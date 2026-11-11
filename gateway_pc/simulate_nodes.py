
import json
import random
import time


def generate_telemetry(device_id):
    return {
        "id": device_id,
        "temp": round(random.uniform(28.0, 40.0), 2),
        "ax": round(random.uniform(-0.2, 0.2), 3),
        "ay": round(random.uniform(-0.2, 0.2), 3),
        "az": round(random.uniform(9.6, 10.0), 3),
        "relay": 0,
        "ai": 0,
    }


def main():
    print("Starting simulated FAN and PUMP nodes...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            for device_id in ("fan", "pump"):
                data = generate_telemetry(device_id)
                print(json.dumps(data))

            print("-" * 50)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nSimulation stopped.")


if __name__ == "__main__":
    main()
