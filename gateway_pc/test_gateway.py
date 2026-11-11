
import json
from copy import deepcopy

from gateway import process_message, node_states


def test_invalid_message(name, raw_message):
    print(f"\n[TEST] {name}")

    before = deepcopy(node_states)

    process_message(raw_message)

    assert node_states == before, (
        f"Failed: invalid message changed node state!"
    )

    print("[PASS] Invalid message was rejected.")


def main():
    print("=== TEST GATEWAY ERROR HANDLING ===")

    test_invalid_message(
        "Invalid JSON",
        "{invalid json"
    )

    test_invalid_message(
        "Missing temperature",
        json.dumps({
            "id": "fan",
            "ax": 0.1,
            "ay": 0.2,
            "az": 9.8,
            "relay": 0,
            "ai": 0
        })
    )

    test_invalid_message(
        "Unknown device",
        json.dumps({
            "id": "motor",
            "temp": 35.0,
            "ax": 0.1,
            "ay": 0.2,
            "az": 9.8,
            "relay": 0,
            "ai": 0
        })
    )

    test_invalid_message(
        "Invalid temperature type",
        json.dumps({
            "id": "pump",
            "temp": "hot",
            "ax": 0.1,
            "ay": 0.2,
            "az": 9.8,
            "relay": 0,
            "ai": 0
        })
    )

    print("\n=== ALL ERROR TESTS PASSED ===")


if __name__ == "__main__":
    main()
