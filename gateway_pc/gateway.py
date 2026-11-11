
import json
import time
from datetime import datetime

from simulate_nodes import generate_telemetry


# Luu du lieu moi nhat cua hai node
node_states = {
    "fan": None,
    "pump": None
}

# Luu thoi diem nhan du lieu hop le gan nhat
last_seen = {
    "fan": None,
    "pump": None
}

# Danh dau node dang bi mat du lieu
node_stale = {
    "fan": False,
    "pump": False
}

STALE_TIMEOUT = 3


def process_message(raw_message):
    try:
        data = json.loads(raw_message)

        required_fields = [
            "id", "temp", "ax", "ay",
            "az", "relay", "ai"
        ]

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing field: {field}")

        device_id = data["id"]

        if device_id not in node_states:
            raise ValueError(f"Unknown device: {device_id}")

        for field in ("temp", "ax", "ay", "az"):
            if type(data[field]) not in (int, float):
                raise ValueError(f"Invalid value: {field}")

        for field in ("relay", "ai"):
            if type(data[field]) is not int:
                raise ValueError(f"Invalid value: {field}")

        data["received_at"] = datetime.now().isoformat(
            timespec="seconds"
        )

        node_states[device_id] = data
        last_seen[device_id] = time.monotonic()

        # Kiem tra node vua phuc hoi ket noi
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

    except (json.JSONDecodeError, ValueError, TypeError) as error:
        print(f"[ERROR] Invalid data: {error}")


def check_stale_nodes():
    now = time.monotonic()

    for device_id in node_states:

        if last_seen[device_id] is None:
            continue

        elapsed = now - last_seen[device_id]

        if elapsed >= STALE_TIMEOUT and not node_stale[device_id]:
            node_stale[device_id] = True

            print(
                f"[STALE] {device_id.upper()} "
                f"has stopped sending data!"
            )


def main():
    print("Starting Python IoT Gateway...")
    print("Mode: SIMULATION")
    print("Testing node disconnection and recovery.\n")
    print("Press Ctrl+C to stop.\n")

    iteration = 0

    try:
        while True:
            for device_id in ("fan", "pump"):

                # Gia lap FAN ngung gui du lieu
                if device_id == "fan" and 5 <= iteration < 11:
                    continue

                data = generate_telemetry(device_id)
                raw_message = json.dumps(data)

                process_message(raw_message)

            check_stale_nodes()

            print("-" * 60)

            iteration += 1
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nGateway stopped.")

        print("\nLatest device states:")
        print(json.dumps(node_states, indent=2))


if __name__ == "__main__":
    main()
