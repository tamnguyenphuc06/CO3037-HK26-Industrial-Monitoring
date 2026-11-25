
import asyncio
import json
import os
import threading
import time

import paho.mqtt.client as mqtt

TOPIC_CONNECT = "v1/gateway/connect"
TOPIC_TELEMETRY = "v1/gateway/telemetry"
TOPIC_ATTRIBUTES = "v1/gateway/attributes"
TOPIC_RPC = "v1/gateway/rpc"


class CoreIoTBridge:
    def __init__(self, loop=None, rpc_handler=None):
        self.host = os.getenv("COREIOT_HOST", "app.coreiot.io").strip()
        self.port = int(os.getenv("COREIOT_PORT", "1883"))
        self.token = os.getenv("COREIOT_TOKEN", "").strip()
        self.tls = os.getenv("COREIOT_TLS", "0") == "1"
        if not self.token:
            raise ValueError("COREIOT_TOKEN is missing; set it in your PowerShell environment")

        self.device_names = {
            "fan": os.getenv("COREIOT_FAN_NAME", "YOLO_FAN_NODE"),
            "pump": os.getenv("COREIOT_PUMP_NAME", "YOLO_PUMP_NODE"),
        }
        self.reverse_names = {name: node for node, name in self.device_names.items()}
        if len(self.reverse_names) != 2:
            raise ValueError("The FAN and PUMP device names in CoreIOT must be distinct")

        self.loop = loop
        self.rpc_handler = rpc_handler
        self.connected = threading.Event()
        self.ble_status = {"fan": False, "pump": False}

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"tv1-pc-gateway-{os.getpid()}",
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(self.token)
        if self.tls:
            self.client.tls_set()  # Use OS CA certificates and validate hostname
        self.client.reconnect_delay_set(min_delay=2, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self):
        print(f"[MQTT] Connecting to {self.host}:{self.port} (TLS={self.tls})")
        self.client.connect_async(self.host, self.port, keepalive=60)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()
        self.connected.clear()

    def wait_connected(self, timeout=15):
        return self.connected.wait(timeout)

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties):
        if reason_code != 0:
            print(f"[MQTT ERROR] Connection rejected: {reason_code}")
            self.connected.clear()
            return
        print("[MQTT CONNECTED] CoreIOT")
        self.connected.set()
        client.subscribe(TOPIC_RPC, qos=1)
        for node_id, name in self.device_names.items():
            # Announce subdevices to enable per-device telemetry and RPC routing.
            client.publish(TOPIC_CONNECT, json.dumps({"device": name}), qos=1)
            self._publish_ble_status(node_id)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _properties):
        self.connected.clear()
        print(f"[MQTT DISCONNECTED] {reason_code}; automatic retry enabled")

    def _on_message(self, _client, _userdata, message):
        if message.topic != TOPIC_RPC:
            return
        try:
            request = json.loads(message.payload.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("RPC payload must be an object")
            node_id = self.reverse_names.get(request.get("device"))
            data = request.get("data")
            if node_id is None or not isinstance(data, dict):
                raise ValueError("Unknown device or missing RPC data")
            if "method" not in data:
                return
            request_id = data.get("id")
            if type(request_id) is not int:
                raise ValueError("RPC request id must be an integer")
 
            method = data["method"]
            params = data.get("params")

            if method == "setRelay":
                if isinstance(params, dict):
                    params = params.get("on")

                if type(params) is not bool:
                    self.publish_rpc_response(node_id, request_id, {
                        "success": False,
                        "error": "setRelay requires true/false"
                    })
                    return

            elif method == "setFanPWM":
                if node_id != "fan":
                    self.publish_rpc_response(node_id, request_id, {
                        "success": False,
                        "error": "PWM only supported for FAN"
                    })
                    return

                if isinstance(params, dict):
                    params = params.get("pwm")

                if type(params) is not int or not 0 <= params <= 255:
                    self.publish_rpc_response(node_id, request_id, {
                        "success": False,
                        "error": "PWM must be an integer from 0 to 255"
                    })
                    return

            else:
                self.publish_rpc_response(node_id, request_id, {
                    "success": False,
                    "error": "Unsupported RPC method"
                })
                return

            if self.loop is None or self.rpc_handler is None:
                self.publish_rpc_response(node_id, request_id, {
                    "success": False,
                    "error": "BLE control unavailable"
                })
                return

            future = asyncio.run_coroutine_threadsafe(
                self._handle_rpc(node_id, request_id, params, method=method),
                self.loop
            )
           
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            print(f"[MQTT RPC INVALID] {exc}")

            print(f"[MQTT RPC INVALID] {exc}")

    @staticmethod
    def _report_rpc_task_error(future):
        try:
            future.result()
        except Exception as exc:
            print(f"[MQTT RPC TASK ERROR] {exc}")

 
    async def _handle_rpc(self, node_id, request_id, value, method="setRelay"):
        try:
            result = await self.rpc_handler(node_id, value, method=method)
            if not isinstance(result, dict):
                result = {"success": bool(result)}
        except Exception as exc:
            result = {"success": False, "error": str(exc)}

        self.publish_rpc_response(node_id, request_id, result)

    def publish_rpc_response(self, node_id, request_id, response):
        self._publish(TOPIC_RPC, {
            "device": self.device_names[node_id],
            "id": request_id,
            "data": response,
        })
        print(f"[MQTT RPC RESPONSE] {node_id.upper()}: {response}")

    def _publish(self, topic, data):
        if not self.connected.is_set():
            print(f"[MQTT OFFLINE] Skipped publish to {topic}")
            return False
        result = self.client.publish(topic, json.dumps(data), qos=1, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT ERROR] Publish enqueue failed: {result.rc}")
            return False
        return True

    def publish_telemetry(self, node_id, data):
        """Call ONLY with already validated telemetry from gateway.process_message."""
        values = {field: data[field] for field in (
            "id", "temp", "ax", "ay", "az", "relay", "ai"
        )}
        if node_id == "fan" and "pwm" in data:
         values["pwm"] = data["pwm"]
        payload = {self.device_names[node_id]: [{
            "ts": int(time.time() * 1000),
            "values": values,
        }]}
        if self._publish(TOPIC_TELEMETRY, payload):
            print(f"[MQTT QUEUED] {node_id.upper()} telemetry")

    def publish_ble_status(self, node_id, online):
        self.ble_status[node_id] = bool(online)
        self._publish_ble_status(node_id)

    def _publish_ble_status(self, node_id):
        self._publish(TOPIC_ATTRIBUTES, {
            self.device_names[node_id]: {"ble_connected": self.ble_status[node_id]}
        })


def main():
    import sys
    if "--test" not in sys.argv:
        print("Run: python gateway_pc/mqtt_bridge.py --test")
        return
    try:
        bridge = CoreIoTBridge()
    except ValueError as exc:
        print(f"[CONFIG ERROR] {exc}")
        return
    try:
        bridge.start()
        if not bridge.wait_connected(15):
            print("[TEST FAILED] Cannot connect to CoreIOT; check host, port and gateway token")
            return
        for node_id in ("fan", "pump"):
            bridge.publish_telemetry(node_id, {
                "id": node_id,
                "temp": 30.5 if node_id == "fan" else 31.5,
                "ax": 0.1, "ay": 0.2, "az": 9.81,
                "relay": 0, "ai": 0,
            })
        print("[MQTT TEST] Sample FAN/PUMP data queued. Verify Latest telemetry on CoreIOT.")
        time.sleep(3)
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
