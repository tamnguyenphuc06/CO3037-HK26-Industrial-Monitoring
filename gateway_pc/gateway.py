
import json
import math
import time
from datetime import datetime


# Luu du lieu moi nhat cua FAN va PUMP
node_states = {
    "fan": None,
    "pump": None
}

# Thoi diem nhan telemetry hop le gan nhat
last_seen = {
    "fan": None,
    "pump": None
}

# Trang thai mat du lieu
node_stale = {
    "fan": False,
    "pump": False
}

STALE_TIMEOUT = 3

# Dem ban tin hop le de xac nhan lenh dieu khien
message_count = dict.fromkeys(node_states, 0)

# Thoi diem bat dau BLE Notify
notify_since = dict.fromkeys(node_states, None)


def mark_notify_started(node_id):
    # Moi phien Notify phai cho telemetry moi, khong dung thoi diem cu.
    notify_since[node_id] = time.monotonic()
    last_seen[node_id] = None


def mark_disconnected(node_id):
    # Ngat BLE: du lieu cu khong con duoc coi la FRESH.
    notify_since[node_id] = None
    node_stale[node_id] = True


def telemetry_status(node_id):
    if node_stale[node_id]:
        return "STALE"

    if last_seen[node_id] is None:
        return "NO DATA"

    elapsed = time.monotonic() - last_seen[node_id]

    return "FRESH" if elapsed < STALE_TIMEOUT else "STALE"


def process_message(raw_message):
    try:
        data = json.loads(raw_message)

        if not isinstance(data, dict):
            raise ValueError("JSON message must be an object")

        required_fields = (
            "id", "temp", "ax", "ay",
            "az", "relay", "ai"
        )

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing field: {field}")

        device_id = data["id"]

        if not isinstance(device_id, str) or device_id not in node_states:
            raise ValueError(f"Unknown device: {device_id}")

        for field in ("temp", "ax", "ay", "az"):
            value = data[field]

            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"Invalid value: {field}")

        for field in ("relay", "ai"):
            if type(data[field]) is not int:
                raise ValueError(f"Invalid value: {field}")

        if data["relay"] not in (0, 1):
            raise ValueError("relay must be 0 or 1")

        data["received_at"] = datetime.now().isoformat(
            timespec="seconds"
        )

        node_states[device_id] = data
        last_seen[device_id] = time.monotonic()
        message_count[device_id] += 1

        if node_stale[device_id]:
            print(f"[RECOVERED] {device_id.upper()} is back online")
            node_stale[device_id] = False

        print(
            f"[OK] {device_id.upper()} | "
            f"Temp: {data['temp']} C | "
            f"Accel: ({data['ax']}, "
            f"{data['ay']}, {data['az']}) | "
            f"Relay: {data['relay']} | "
            f"AI: {data['ai']}"
        )

        return True

    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        print(f"[ERROR] Invalid data: {error}")
        return False


def check_stale_nodes():
    now = time.monotonic()

    for device_id in node_states:
        reference = last_seen[device_id]

        if reference is None:
            reference = notify_since[device_id]

        if reference is None:
            continue

        elapsed = now - reference

        if elapsed >= STALE_TIMEOUT and not node_stale[device_id]:
            node_stale[device_id] = True

            print(
                f"[STALE] {device_id.upper()} "
                f"has stopped sending data!"
            )
