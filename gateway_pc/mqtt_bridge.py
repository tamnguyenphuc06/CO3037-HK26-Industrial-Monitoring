
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

TOPIC_ATTR_REQUEST = "v1/gateway/attributes/request"
TOPIC_ATTR_RESPONSE = "v1/gateway/attributes/response"

FAN_PROTECTION_KEYS = (
    "protection_requested",
    "protection_phase",
    "protection_alarm_active"
)



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

        # FAN Protection - Shared Attributes
        self.fan_shared = {}
        self.fan_shared_synced = threading.Event()
        self.fan_attr_request_id = 0
        self.fan_shared_lock = threading.RLock()
        self.fan_snapshot_timer = None
        self.fan_response_sub_mid = None
        self.fan_connection_generation = 0
        self.fan_request_timestamp = None
        self.fan_snapshot_attempts = 0
        # Newer servers accept "sharedKeys"; older ones need "client": false and "keys".
        self.fan_attr_format = os.getenv("COREIOT_ATTR_FORMAT", "legacy").strip().lower()
        if self.fan_attr_format not in ("legacy", "new"):
            raise ValueError("COREIOT_ATTR_FORMAT must be 'legacy' or 'new'")
        self.fan_snapshot_disabled = False


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
        self.client.on_subscribe = self._on_subscribe  # Trigger FAN snapshot after SUBACK

    def start(self):
        print(f"[MQTT] Connecting to {self.host}:{self.port} (TLS={self.tls})")
        self.client.connect_async(self.host, self.port, keepalive=60)
        self.client.loop_start()

    def stop(self):
        self._cancel_fan_snapshot_timer()
        self.client.disconnect()
        self.client.loop_stop()
        self.connected.clear()

    def wait_connected(self, timeout=15):
        return self.connected.wait(timeout)

    def _cancel_fan_snapshot_timer(self):
        if self.fan_snapshot_timer is not None:
            self.fan_snapshot_timer.cancel()
            self.fan_snapshot_timer = None

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties):
        if reason_code != 0:
            print(f"[MQTT ERROR] Connection rejected: {reason_code}")
            self.connected.clear()
            return

        print("[MQTT CONNECTED] CoreIOT")
        self.connected.set()
        self.fan_connection_generation += 1
        self._cancel_fan_snapshot_timer()
        with self.fan_shared_lock:
            self.fan_shared_synced.clear()
            self.fan_shared = {}

        client.subscribe(TOPIC_RPC, qos=1)
        client.subscribe(TOPIC_ATTRIBUTES, qos=1)
        rc, mid = client.subscribe(TOPIC_ATTR_RESPONSE, qos=1)
        self.fan_response_sub_mid = mid if rc == mqtt.MQTT_ERR_SUCCESS else None

        # Gateway connect must be published before asking for device attributes.
        for node_id, name in self.device_names.items():
            client.publish(TOPIC_CONNECT, json.dumps({"device": name}), qos=1)
            self._publish_ble_status(node_id)

        if self.fan_response_sub_mid is None:
            print("[FAN GUARD] Cannot subscribe to attribute responses; RESET BLOCKED")
        elif self.fan_snapshot_disabled:
            print("[FAN GUARD] Attribute snapshots disabled after broker rejection; RESET BLOCKED")

    def _on_subscribe(self, _client, _userdata, mid, reason_codes, _properties):
        # Wait for SUBACK of the attribute response topic. This eliminates the
        # subscribe/request race present in the previous version.
        if mid != self.fan_response_sub_mid:
            return
        if any(getattr(code, "is_failure", isinstance(code, int) and code >= 128) for code in reason_codes):
            print("[FAN GUARD] Attribute response subscription rejected; RESET BLOCKED")
            return
        if self.fan_snapshot_disabled:
            return
        generation = self.fan_connection_generation
        print("[FAN SNAPSHOT] Response subscription confirmed; sending snapshot request in 2 seconds")
        # Allow the preceding v1/gateway/connect message to be processed.
        self.fan_snapshot_timer = threading.Timer(
            2.0, self._request_fan_attributes, args=(generation,)
        )
        self.fan_snapshot_timer.daemon = True
        self.fan_snapshot_timer.start()

    def _request_fan_attributes(self, generation):
        if not self.connected.is_set() or generation != self.fan_connection_generation:
            return
        if self.fan_snapshot_disabled or self.fan_shared_synced.is_set():
            return
        self.fan_attr_request_id += 1
        payload = {"id": self.fan_attr_request_id, "device": self.device_names["fan"]}
        if self.fan_attr_format == "legacy":
            payload.update({"keys": list(FAN_PROTECTION_KEYS), "client": False})
        else:
            payload["sharedKeys"] = ",".join(FAN_PROTECTION_KEYS)
        if self._publish(TOPIC_ATTR_REQUEST, payload):
            self.fan_request_timestamp = time.monotonic()
            self.fan_snapshot_attempts += 1
            print(f"[FAN SNAPSHOT] Requested Shared Attributes ({self.fan_attr_format})")
            timer = threading.Timer(8.0, self._report_snapshot_timeout,
                                    args=(generation, self.fan_attr_request_id))
            timer.daemon = True
            timer.start()

    def _report_snapshot_timeout(self, generation, request_id):
        if (self.connected.is_set() and generation == self.fan_connection_generation
                and request_id == self.fan_attr_request_id
                and not self.fan_shared_synced.is_set()):
            print("[FAN GUARD] No complete attribute snapshot; RESET BLOCKED. "
                  "Check FAN Shared Attributes and COREIOT_ATTR_FORMAT.")

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _properties):
        self.connected.clear()
        self._cancel_fan_snapshot_timer()
        self.fan_connection_generation += 1
        with self.fan_shared_lock:
            self.fan_shared_synced.clear()
            self.fan_shared = {}
        # If the server closed the connection right after the attribute
        # request, try the other documented API format ONCE; never loop forever.
        if (self.fan_request_timestamp is not None
                and time.monotonic() - self.fan_request_timestamp < 8.0
                and not self.fan_snapshot_disabled):
            if self.fan_snapshot_attempts == 1:
                self.fan_attr_format = "new" if self.fan_attr_format == "legacy" else "legacy"
                print(f"[FAN SNAPSHOT] Broker closed connection; trying {self.fan_attr_format} format once")
            else:
                self.fan_snapshot_disabled = True
                print("[FAN GUARD] Both attribute request formats failed; "
                      "snapshot disabled, RESET BLOCKED")
        self.fan_request_timestamp = None
        print(f"[MQTT DISCONNECTED] {reason_code}; automatic retry enabled")

    def _on_message(self, _client, _userdata, message):
        
        if message.topic in (TOPIC_ATTRIBUTES, TOPIC_ATTR_RESPONSE):
            try:
                data = json.loads(message.payload.decode("utf-8"))
                if not isinstance(data, dict) or data.get("device") != self.device_names["fan"]:
                    return

                if message.topic == TOPIC_ATTR_RESPONSE:
                    if data.get("id") != self.fan_attr_request_id:
                        return
                    attrs = data.get("shared", data.get("values", {}))
                    if not isinstance(attrs, dict):
                        print("[FAN GUARD] Unexpected attribute response:", data)
                        return
                    # The initial snapshot must be complete and strongly typed.
                    if not all(k in attrs for k in FAN_PROTECTION_KEYS):
                        print("[FAN GUARD] Missing Shared Attributes:",
                              sorted(set(FAN_PROTECTION_KEYS) - set(attrs)))
                        return
                    if not self._valid_fan_attributes(attrs):
                        print("[FAN GUARD] Wrong Shared Attribute types; RESET BLOCKED")
                        return
                    with self.fan_shared_lock:
                        self.fan_shared = {k: attrs[k] for k in FAN_PROTECTION_KEYS}
                        self.fan_shared_synced.set()
                    self.fan_request_timestamp = None
                    print("[FAN GUARD] SYNCED:", self.fan_shared)
                else:
                    attrs = data.get("data", {})
                    if not isinstance(attrs, dict):
                        return
                    updates = {k: v for k, v in attrs.items()
                               if k in FAN_PROTECTION_KEYS}
                    if not updates:
                        return
                    with self.fan_shared_lock:
                        if not self.fan_shared_synced.is_set():
                            print("[FAN GUARD] Attribute update received; awaiting full snapshot")
                            return
                        updated = {**self.fan_shared, **updates}
                        if not self._valid_fan_attributes(updated):
                            self.fan_shared_synced.clear()
                            print("[FAN GUARD] Invalid update; RESET BLOCKED")
                            return
                        self.fan_shared = updated
                    print("[FAN GUARD] Updated:", self.fan_shared)
            except (ValueError, TypeError, UnicodeDecodeError) as exc:
                print("[FAN SHARED ERROR]", exc)
            return

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
          
            elif method == "setFanProtection":
                if node_id != "fan":
                    self.publish_rpc_response(node_id, request_id, {
                        "success": False,
                        "error": "Protection only supported for FAN"
                    })
                    return

                if not isinstance(params, dict) or params.get("locked") is not True:
                    self.publish_rpc_response(node_id, request_id, {
                        "success": False,
                        "error": "Protection requires locked=true"
                    })
                    return

                params = True

            elif method == "resetFanProtection":
                if node_id != "fan":
                    self.publish_rpc_response(node_id, request_id, {
                        "success": False,
                        "error": "Reset only supported for FAN"
                    })
                    return

                if params is not None and params != {}:
                    self.publish_rpc_response(node_id, request_id, {
                        "success": False,
                        "error": "Reset requires empty params"
                    })
                    return

                guard_error = self._reset_guard_error()
                if guard_error:
                    self.publish_rpc_response(node_id, request_id, {
                        "success": False, "error": guard_error
                    })
                    print(f"[FAN GUARD] Reset denied: {guard_error}")
                    return
                params = None

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
            future.add_done_callback(self._report_rpc_task_error)

        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            print(f"[MQTT RPC INVALID] {exc}")

    @staticmethod
    def _valid_fan_attributes(attrs):
        return (type(attrs.get("protection_requested")) is bool
                and isinstance(attrs.get("protection_phase"), str)
                and type(attrs.get("protection_alarm_active")) is bool)

    def _reset_guard_error(self):
        with self.fan_shared_lock:
            if not self.fan_shared_synced.is_set():
                return "Protection state not synchronized; reset denied"
            state = self.fan_shared.copy()
        if not (state.get("protection_requested") is True
                and state.get("protection_phase") == "WAIT_RESET"
                and state.get("protection_alarm_active") is False):
            return "Protection is not in WAIT_RESET with alarm cleared"
        return None

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
        
        if (
            node_id == "fan"
            and method == "resetFanProtection"
            and result.get("success") is True
            and result.get("protection_locked") is False
        ):
            queued = self._publish(TOPIC_TELEMETRY, {
                self.device_names["fan"]: [{
                    "ts": int(time.time() * 1000),
                    "values": {
                        "fan_reset_ack": True,
                        "protection_locked": False,
                        "pwm": 0
                    }
                }]
            })

            if not queued:
                result = {
                    "success": False,
                    "error": "ESP32 reset OK, CoreIOT sync failed"
                }

        if (node_id == "fan" and method == "resetFanProtection"
                and result.get("success") is True
                and result.get("protection_locked") is False):
            # Await fresh CoreIOT attributes before permitting another reset.
            with self.fan_shared_lock:
                self.fan_shared["protection_phase"] = "RESET_ACK_PENDING_CLOUD"
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
        
        if node_id == "fan":
            if "pwm" in data:
                values["pwm"] = data["pwm"]

            if type(data.get("protection_locked")) is bool:
                values["protection_locked"] = data["protection_locked"]

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
