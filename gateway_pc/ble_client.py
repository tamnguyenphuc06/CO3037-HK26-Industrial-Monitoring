import asyncio
import json
import sys
import threading
import time

from bleak import BleakClient, BleakScanner
from gateway import (
    check_stale_nodes, mark_disconnected, mark_notify_started,
    message_count, node_states, process_message, telemetry_status,
)

BLE_CONFIG = {
    "fan": {
        "name": "YOLO_FAN_NODE",
        "id": "fan",
        "service_uuid": "4fafc201-1fb5-459e-8fcc-c5c9c331914b",
        "telemetry_uuid": "beb5483e-36e1-4688-b7f5-ea07361b26a8",
        "command_uuid": "1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e",
    },
    "pump": {
        "name": "YOLO_PUMP_NODE",
        "id": "pump",
        "service_uuid": "5bcfa202-2fc6-469f-9fdd-d6d0d442925c",
        "telemetry_uuid": "ceb6594f-47f2-4799-c8f6-fb18472c37b9",
        "command_uuid": "2d06e6f4-e908-424b-cf4e-8b3f6e8cf98f",
    },
}
CONNECTED = {}
SCAN_TIMEOUT = 5.0
RETRY_DELAY = 3.0
ACK_TIMEOUT = 5.0
# Prevent simultaneous console and cloud RPC commands for the same ESP32.
COMMAND_LOCKS = {"fan": asyncio.Lock(), "pump": asyncio.Lock()}


def load_config():
    return BLE_CONFIG


async def scan_ble_nodes(config, timeout=10.0):
    print(f"[SCAN] Searching for {', '.join(config).upper()} ({timeout:g} seconds)...")
    devices = await BleakScanner.discover(timeout=timeout)
    found = {}
    for node_id, info in config.items():
        device = next((dev for dev in devices if dev.name == info["name"]), None)
        if device is None:
            print(f"[NOT FOUND] {node_id.upper()} ({info['name']})")
        else:
            found[node_id] = device
            print(f"[FOUND] {node_id.upper()} ({device.name})")
    return found


def make_notify_callback(expected_id, bridge=None):
    def callback(_sender, data):
        try:
            raw = bytes(data).decode("utf-8")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or payload.get("id") != expected_id:
                print(f"[REJECTED] Invalid node id on {expected_id.upper()} connection")
                return
            if process_message(raw) and bridge is not None:
                bridge.publish_telemetry(expected_id, node_states[expected_id])
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            print(f"[INVALID BLE] {expected_id.upper()}: {exc}")
    return callback


def build_command(turn_on):
    return json.dumps({"cmd": "RELAY_ON" if turn_on else "RELAY_OFF"}).encode("utf-8")

def build_pwm_command(duty):
    if type(duty) is not int or not 0 <= duty <= 255:
        raise ValueError("PWM must be an integer from 0 to 255")

    return json.dumps({
        "cmd": "SET_FAN_PWM",
        "value": duty
    }).encode("utf-8")

async def send_command(client, node_info, turn_on):
    node_id = node_info["id"]
    expected = int(turn_on)
    previous = node_states.get(node_id)
    previous_relay = previous.get("relay") if previous else None
    previously_fresh = telemetry_status(node_id) == "FRESH"
    payload = build_command(turn_on)
    await asyncio.wait_for(
        client.write_gatt_char(node_info["command_uuid"], payload, response=True),
        timeout=ACK_TIMEOUT,
    )
    print(f"[WRITE OK] {node_info['name']}: {payload.decode('utf-8')}")

    # Chi dung telemetry moi SAU khi GATT write ket thuc; khong dung cache cu.
    baseline = message_count[node_id]
    deadline = time.monotonic() + ACK_TIMEOUT
    while time.monotonic() < deadline:
        if CONNECTED.get(node_id) is not client or not client.is_connected:
            print(f"[UNCONFIRMED] {node_id.upper()}: disconnected before confirmation")
            return False
        state = node_states.get(node_id)
        if (message_count[node_id] > baseline and state is not None
                and state["relay"] == expected
                and telemetry_status(node_id) == "FRESH"):
            print(f"[STATE CONFIRMED] {node_id.upper()} | Relay: {expected} (new telemetry)")
            if previously_fresh and previous_relay != expected:
                print(f"[STATE CHANGED] {node_id.upper()} | {previous_relay} -> {expected}")
            else:
                print("[INFO] Target state observed; a state transition was not established")
            return True
        await asyncio.sleep(0.1)
    print(f"[UNCONFIRMED] {node_id.upper()}: no matching fresh telemetry within {ACK_TIMEOUT:g}s")
    return False

async def send_pwm_command(client, node_info, duty):
    if node_info["id"] != "fan":
        raise ValueError("PWM only supported for FAN")

    state = node_states.get("fan") or {}

    # Khi chua xac minh mo khoa, chi cho phep PWM = 0
    if duty > 0:
        if (
            telemetry_status("fan") != "FRESH"
            or state.get("protection_locked") is not False
        ):
            print("[PWM REJECTED] FAN locked or unconfirmed")
            return False

    payload = build_pwm_command(duty)

    await asyncio.wait_for(
        client.write_gatt_char(
            node_info["command_uuid"],
            payload,
            response=True
        ),
        timeout=ACK_TIMEOUT
    )

    # Chi chap nhan telemetry moi sau BLE Write
    baseline = message_count["fan"]
    deadline = time.monotonic() + ACK_TIMEOUT

    while time.monotonic() < deadline:
        state = node_states.get("fan") or {}

        if not client.is_connected:
            return False

        if (
            message_count["fan"] > baseline
            and telemetry_status("fan") == "FRESH"
            and state.get("pwm") == duty
            and (
                duty == 0
                or state.get("protection_locked") is False
            )
        ):
            print(f"[PWM CONFIRMED] FAN PWM={duty}")
            return True

        await asyncio.sleep(0.1)

    print("[PWM FAILED] No telemetry confirmation")
    return False

async def send_fan_protection_command(client, node_info, locked):
    if node_info["id"] != "fan":
        return False

    command = (
        "FAN_PROTECTION_LOCK"
        if locked else "FAN_PROTECTION_RESET"
    )

    payload = json.dumps({"cmd": command}).encode("utf-8")
    baseline = message_count["fan"]

    await asyncio.wait_for(
        client.write_gatt_char(
            node_info["command_uuid"],
            payload,
            response=True
        ),
        timeout=ACK_TIMEOUT
    )

    # Cho telemetry moi xac nhan ESP32 da thuc thi
    deadline = time.monotonic() + ACK_TIMEOUT

    while time.monotonic() < deadline:
        state = node_states.get("fan")

        if (
            client.is_connected
            and message_count["fan"] > baseline
            and telemetry_status("fan") == "FRESH"
            and state is not None
            and type(state.get("protection_locked")) is bool
            and state["protection_locked"] == locked
            and state.get("pwm") == 0
        ):
            print(f"[FAN] Protection confirmed: {locked}")
            return True

        await asyncio.sleep(0.1)

    print("[FAN] Protection confirmation timeout")
    return False

async def receive_node(node_id, device, info, bridge=None):
    try:
        print(f"[CONNECTING] {node_id.upper()}")
        async with BleakClient(device, timeout=20.0) as client:
            service = client.services.get_service(info["service_uuid"])
            if service is None:
                raise ValueError(f"{node_id}: BLE service UUID not found")
            chars = {char.uuid.lower(): char for char in service.characteristics}
            for key, prop in (("telemetry_uuid", "notify"), ("command_uuid", "write")):
                char = chars.get(info[key].lower())
                if char is None or prop not in char.properties:
                    raise ValueError(f"{node_id}: {key} missing or lacks {prop}")
            mark_notify_started(node_id)
            await client.start_notify(info["telemetry_uuid"], make_notify_callback(node_id, bridge))
            CONNECTED[node_id] = client
            print(f"[CONNECTED] {node_id.upper()} + NOTIFY")
            if bridge is not None:
                bridge.publish_ble_status(node_id, True)
            while client.is_connected:
                await asyncio.sleep(0.5)
            print(f"[DISCONNECTED] {node_id.upper()}")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"[BLE ERROR] {node_id.upper()}: {exc}")
    finally:
        CONNECTED.pop(node_id, None)
        mark_disconnected(node_id)
        if bridge is not None:
            bridge.publish_ble_status(node_id, False)


async def connection_manager(config, bridge=None):
    tasks = {}
    try:
        while True:
            for node_id, task in list(tasks.items()):
                if task.done():
                    await task
                    del tasks[node_id]
                    print(f"[RECONNECT] {node_id.upper()}: waiting for advertising")
            missing = {node: info for node, info in config.items() if node not in tasks}
            if missing:
                try:
                    found = await scan_ble_nodes(missing, SCAN_TIMEOUT)
                    for node, device in found.items():
                        tasks[node] = asyncio.create_task(receive_node(node, device, config[node], bridge))
                except Exception as exc:
                    print(f"[SCAN ERROR] {exc}; will retry")
            await asyncio.sleep(RETRY_DELAY if missing else 0.5)
    finally:
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)


async def stale_monitor():
    # Doc lap voi ket noi BLE: tiep tuc kiem tra ngay ca khi mat ca hai node.
    while True:
        check_stale_nodes()
        await asyncio.sleep(0.5)


async def command_console(config):
    print("[COMMANDS] fan on | fan off | pump on | pump off | status | quit")
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    stop_reader = threading.Event()

    def read_commands():
        while not stop_reader.is_set():
            try:
                command = input("gateway> ").strip().lower()
            except (EOFError, OSError):
                command = "quit"
            try:
                loop.call_soon_threadsafe(queue.put_nowait, command)
            except RuntimeError:
                return
            if command in ("quit", "exit"):
                return

    threading.Thread(target=read_commands, daemon=True).start()
    try:
        while True:
            command = await queue.get()
            if command in ("quit", "exit"):
                return
            if command == "status":
                for node_id in config:
                    client = CONNECTED.get(node_id)
                    online = bool(client and client.is_connected)
                    print(f"{node_id.upper()}: {'BLE CONNECTED' if online else 'BLE OFFLINE'}; "
                          f"telemetry={telemetry_status(node_id)}; latest={node_states.get(node_id)}")
                continue

            parts = command.split()

            if len(parts) == 3 and parts[0] == "fan" and parts[1] == "pwm":
                try:
                    duty = int(parts[2])

                    if not 0 <= duty <= 255:
                        print("[INVALID] PWM must be 0-255")
                        continue

                    client = CONNECTED.get("fan")

                    if client is None or not client.is_connected:
                        print("[OFFLINE] FAN: cannot send PWM")
                        continue

                    async with COMMAND_LOCKS["fan"]:
                        await send_pwm_command(client, config["fan"], duty)

                except ValueError:
                    print("[INVALID] PWM must be an integer")
                except Exception as exc:
                    print(f"[PWM ERROR] FAN: {exc}")

                continue

            if len(parts) != 2 or parts[0] not in config or parts[1] not in ("on", "off"):
                print("[INVALID] Use: fan on | fan off | pump on | pump off | status | quit")
                continue
            node_id, action = parts
            client = CONNECTED.get(node_id)
            if client is None or not client.is_connected:
                print(f"[OFFLINE] {node_id.upper()}: cannot send BLE command")
                continue
            try:
                async with COMMAND_LOCKS[node_id]:
                    await send_command(client, config[node_id], action == "on")
            except Exception as exc:
                print(f"[COMMAND ERROR] {node_id.upper()}: {exc}")
    finally:
        stop_reader.set()


async def main():
    config = load_config()
    if "--scan" in sys.argv:
        await scan_ble_nodes(config)
        return

    bridge = None
    if "--mqtt" in sys.argv:
        from mqtt_bridge import CoreIoTBridge


        async def cloud_rpc(node_id, value, method="setRelay"):
            info = config[node_id]
            client = CONNECTED.get(node_id)

            if client is None or not client.is_connected:
                return {"success": False, "error": f"{node_id.upper()} BLE offline"}

            if method in ("setFanProtection", "resetFanProtection"):
                if node_id != "fan":
                    return {
                        "success": False,
                        "error": "Only FAN supports protection"
                    }

                if method == "setFanProtection":
                    if value is not True:
                        return {
                            "success": False,
                            "error": "Invalid lock request"
                        }
                    # Lock is always allowed, even when MQTT attributes are stale.
                    locked = True
                else:
                    # RESET: verify CoreIOT shared state and fresh FAN telemetry.
                    if (
                        bridge is None
                        or not bridge.connected.is_set()
                        or not bridge.fan_shared_synced.is_set()
                    ):
                        return {
                            "success": False,
                            "error": "CoreIOT state not synchronized"
                        }

                    shared = bridge.fan_shared
                    if (
                        shared.get("protection_requested") is not True
                        or shared.get("protection_phase") != "WAIT_RESET"
                        or shared.get("protection_alarm_active") is not False
                    ):
                        return {
                            "success": False,
                            "error": "FAN is not ready for Reset"
                        }

                    state = node_states.get("fan") or {}
                    if (
                        telemetry_status("fan") != "FRESH"
                        or state.get("protection_locked") is not True
                        or state.get("pwm") != 0
                    ):
                        return {
                            "success": False,
                            "error": "FAN lock state not confirmed"
                        }

                    locked = False

                async with COMMAND_LOCKS["fan"]:
                    # Recheck before releasing the lock if commands were queued.
                    if not locked:
                        if (
                            bridge is None
                            or not bridge.connected.is_set()
                            or not bridge.fan_shared_synced.is_set()
                            or bridge.fan_shared.get("protection_requested") is not True
                            or bridge.fan_shared.get("protection_phase") != "WAIT_RESET"
                            or bridge.fan_shared.get("protection_alarm_active") is not False
                            or telemetry_status("fan") != "FRESH"
                            or (node_states.get("fan") or {}).get("protection_locked") is not True
                            or (node_states.get("fan") or {}).get("pwm") != 0
                            or not client.is_connected
                        ):
                            return {
                                "success": False,
                                "error": "FAN Reset conditions changed"
                            }
                    confirmed = await send_fan_protection_command(
                        client, info, locked
                    )

                return {
                    "success": confirmed,
                    "protection_locked": locked if confirmed else None
                }

            if method == "setFanPWM":
                if node_id != "fan":
                    return {"success": False, "error": "PWM only supported for FAN"}
                if type(value) is not int or not 0 <= value <= 255:
                    return {"success": False, "error": "Invalid PWM value"}

                # Prevent PWM > 0 while the CoreIOT lock is active/unknown.
                if value > 0:
                    if bridge is None or not bridge.fan_shared_synced.is_set():
                        return {
                            "success": False,
                            "error": "Protection state not synchronized"
                        }
                    if bridge.fan_shared.get("protection_requested") is not False:
                        return {
                            "success": False,
                            "error": "FAN protection is active"
                        }

                async with COMMAND_LOCKS["fan"]:
                    confirmed = await send_pwm_command(client, info, value)
                if not confirmed:
                    return {
                        "success": False,
                        "error": "PWM rejected or not confirmed"
                    }
                return {"success": True, "pwm": value}

            if method == "setRelay":
                async with COMMAND_LOCKS[node_id]:
                    confirmed = await send_command(client, info, value)
                if not confirmed:
                    return {"success": False, "error": "Relay state not confirmed"}
                return {"success": True, "relay": int(value)}

            return {"success": False, "error": "Unsupported RPC method"}

        bridge = CoreIoTBridge(
            loop=asyncio.get_running_loop(),
            rpc_handler=cloud_rpc
        )
        bridge.start()

    tasks = [
        asyncio.create_task(connection_manager(config, bridge)),
        asyncio.create_task(stale_monitor()),
    ]

    try:
        if "--control" in sys.argv:
            await command_console(config)
        else:
            await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        if bridge is not None:
            bridge.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] BLE client stopped")
