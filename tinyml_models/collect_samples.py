"""Collect 3-axis MPU6050 acceleration CSV from ESP32-S3 (fan node).

Expected Serial line from sensors.cpp::streamVibrationSampleSerial():
    timestamp_ms,ax,ay,az
For example:
    120,0.0123,-0.1234,9.8123

Place this file under tinyml/scripts/ to save into tinyml/dataset/<label>/.
If your directory layout differs, adjust DATASET_DIR below.
"""

import math
import re
import sys
import time
from pathlib import Path

import serial
import serial.tools.list_ports

BAUD_RATE = 115200
DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"


def select_serial_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("[LỖI] Không tìm thấy cổng COM. Kiểm tra cáp USB và driver.")
        sys.exit(1)

    print("\nDanh sách cổng COM:")
    for index, port in enumerate(ports, 1):
        print(f"  [{index}] {port.device} - {port.description}")

    while True:
        try:
            choice = int(input("Chọn số thứ tự cổng COM: "))
            if 1 <= choice <= len(ports):
                return ports[choice - 1].device
        except ValueError:
            pass
        print("[LỖI] Vui lòng nhập số thứ tự hợp lệ.")


def read_positive_int(prompt):
    while True:
        try:
            value = int(input(prompt))
            if value > 0:
                return value
        except ValueError:
            pass
        print("[LỖI] Hãy nhập số nguyên dương.")


def parse_sample(line):
    """Return ESP32 millis timestamp or None if Serial line is not valid CSV data."""
    parts = line.split(",")
    if len(parts) != 4:
        return None
    try:
        timestamp_ms = int(parts[0].strip())
        values = [float(value.strip()) for value in parts[1:]]
    except ValueError:
        return None

    if timestamp_ms < 0 or not all(math.isfinite(value) for value in values):
        return None
    return timestamp_ms


def collect_vibration_data():
    port_name = select_serial_port()

    label = input("Nhập nhãn trạng thái (ví dụ: fan_normal): ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", label):
        print("[LỖI] Nhãn chỉ được chứa chữ không dấu, số, dấu _ hoặc -.")
        return

    duration_sec = read_positive_int("Nhập thời gian thu mẫu (giây, ví dụ 10): ")
    sample_id = read_positive_int("Nhập số thứ tự mẫu (ví dụ 1): ")

    output_dir = DATASET_DIR / label
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"{label}_{sample_id:03d}.csv"

    try:
        with serial.Serial(port_name, BAUD_RATE, timeout=0.25) as ser:
            time.sleep(2)  # Cho ESP32 ổn định nếu mở cổng COM gây reset
            ser.reset_input_buffer()
            print(f"\n[BẮT ĐẦU] Thu '{label}' trong {duration_sec}s từ {port_name}...")

            sample_count = 0
            invalid_count = 0
            first_timestamp = None
            last_timestamp = None
            start_time = time.monotonic()

            with filename.open("w", encoding="utf-8", newline="") as file:
                file.write("timestamp,ax,ay,az\n")
                while time.monotonic() - start_time < duration_sec:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    timestamp = parse_sample(line)
                    if timestamp is None or (
                        last_timestamp is not None and timestamp <= last_timestamp
                    ):
                        invalid_count += 1
                        continue

                    file.write(line + "\n")
                    sample_count += 1
                    if first_timestamp is None:
                        first_timestamp = timestamp
                    last_timestamp = timestamp

            elapsed = time.monotonic() - start_time

    except (serial.SerialException, OSError) as exc:
        print(f"[LỖI] Không thể thu dữ liệu từ {port_name}: {exc}")
        return

    # Đánh giá tần số dựa trên timestamp ESP32, chính xác hơn sample_count / thời gian PC.
    hz_device = 0.0
    if sample_count >= 2 and last_timestamp > first_timestamp:
        hz_device = (sample_count - 1) * 1000.0 / (last_timestamp - first_timestamp)

    print(f"\n[HOÀN TẤT] CSV: {filename}")
    print(f"Mẫu hợp lệ: {sample_count} | Dòng bỏ qua: {invalid_count}")
    print(f"Tần số từ timestamp ESP32: {hz_device:.2f} Hz")
    print(f"Tốc độ ghi trung bình trên PC: {sample_count / elapsed:.2f} mẫu/s")
    if sample_count == 0:
        print("[CẢNH BÁO] CSV rỗng: main.cpp chưa phát dữ liệu qua Serial hoặc sai cổng COM.")
    print("[LƯU Ý] SIMULATE_DATA=1 là dữ liệu giả, không dùng để train mô hình thực.")


if __name__ == "__main__":
    collect_vibration_data()
