"""TV1 BLE client for TV3's fan and pump firmware.

Commands: --scan, --control, or listen-only.
NOTE: BLE writes are not application-level ACKs.
"""
import asyncio
import json
import sys
from pathlib import Path

from bleak import BleakClient, BleakScanner
from gateway import check_stale_nodes, node_states, process_message

CONFIG_PATH = Path(__file__).with_name("ble_config.json")
CONNECTED = {}


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


async def scan_ble_nodes(config):
    print("[SCAN] Searching for FAN and PUMP (10 seconds)...")
    devices = await BleakScanner.discover(timeout=10.0)
    found = {}
    for node_id, info in config.items():
        device = next((dev for dev in devices if dev.name == info["name"]), None)
        if device is None:
            print(f"[NOT FOUND] {node_id.upper()} ({info['name']})")
        else:
            found[node_id] = device
            print(f"[FOUND] {node_id.upper()} ({device.name})")
    return found


def make_notify_callback(expected_id):
    def callback(_sender, data):
        try:
            raw = bytes(data).decode("utf-8")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or payload.get("id") != expected_id:
                print(f"[REJECTED] Invalid node id on {expected_id.upper()} connection")
                return
            process_message(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"[INVALID BLE] {expected_id.upper()}: {exc}")
    return callback


def build_command(turn_on):
    return json.dumps({"cmd": "RELAY_ON" if turn_on else "RELAY_OFF"}).encode("utf-8")


async def send_command(client, node_info, turn_on):
    payload = build_command(turn_on)
    await client.write_gatt_char(node_info["command_uuid"], payload, response=True)
    print(f"[WRITE OK] {node_info['name']}: {payload.decode('utf-8')}")
    print("[INFO] GATT write succeeded; device execution not yet confirmed")


async def receive_node(node_id, device, info):
    try:
        async with BleakClient(device, timeout=20.0) as client:
            # Validate that the service and characteristics match TV3 firmware.
            if not client.services.get_service(info["service_uuid"]):
                raise ValueError(f"{node_id}: BLE service UUID not found")
            for key in ("telemetry_uuid", "command_uuid"):
                if not client.services.get_characteristic(info[key]):
                    raise ValueError(f"{node_id}: {key} not found")
            CONNECTED[node_id] = client
            await client.start_notify(info["telemetry_uuid"], make_notify_callback(node_id))
            print(f"[CONNECTED] {node_id.upper()} + NOTIFY")
            while client.is_connected:
                check_stale_nodes()
                await asyncio.sleep(1)
            print(f"[DISCONNECTED] {node_id.upper()}")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"[BLE ERROR] {node_id.upper()}: {exc}")
    finally:
        CONNECTED.pop(node_id, None)


async def command_console(config):
    print("[COMMANDS] fan on | fan off | pump on | pump off | status | quit")
    while True:
        try:
            command = (await asyncio.to_thread(input, "gateway> ")).strip().lower()
        except EOFError:
            return
        if command in ("quit", "exit"):
            return
        if command == "status":
            for node_id in config:
                client = CONNECTED.get(node_id)
                online = bool(client and client.is_connected)
                print(f"{node_id.upper()}: {'BLE CONNECTED' if online else 'BLE OFFLINE'}; latest={node_states.get(node_id)}")
            continue
        parts = command.split()
        if len(parts) != 2 or parts[0] not in config or parts[1] not in ("on", "off"):
            print("[INVALID] Use: fan on | fan off | pump on | pump off | status | quit")
            continue
        node_id, action = parts
        client = CONNECTED.get(node_id)
        if client is None or not client.is_connected:
            print(f"[OFFLINE] {node_id.upper()}: cannot send BLE command")
            continue
        try:
            await send_command(client, config[node_id], action == "on")
        except Exception as exc:
            print(f"[COMMAND ERROR] {node_id.upper()}: {exc}")


async def main():
    config = load_config()
    found = await scan_ble_nodes(config)
    if "--scan" in sys.argv:
        return
    if not found:
        print("[INFO] No group ESP32 nodes available. Check firmware and power.")
        return
    tasks = [asyncio.create_task(receive_node(node_id, device, config[node_id])) for node_id, device in found.items()]
    try:
        if "--control" in sys.argv:
            await command_console(config)
        else:
            await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] BLE client stopped")
