#ifndef CONFIG_FAN_H
#define CONFIG_FAN_H

// Định danh thiết bị
#define DEVICE_NAME         "YOLO_FAN_NODE"
#define DEVICE_ID           "fan"

// Chân trên Yolo UNO
#define PIN_RELAY           4       // Relay rời, nếu có lắp
#define PIN_DS18B20         1       // D2: dữ liệu DS18B20
#define PIN_I2C_SDA         11      // SDA: cổng I2C cho MPU6050
#define PIN_I2C_SCL         12      // SCL: cổng I2C cho MPU6050
#define PIN_FAN_D3          6       // D3: chân quạt đã thử chạy
#define PIN_FAN_D4          7       // D4: chân quạt đã thử chạy

// Quy ước mức kích Relay (0: Kích LOW, 1: Kích HIGH)
#define RELAY_ACTIVE_LEVEL  LOW     // Đa số module Relay trên thị trường kích mức LOW

// Chu kỳ gửi dữ liệu BLE (miligiây)
#define TELEMETRY_INTERVAL_MS 1000

// Cờ kích hoạt chế độ dữ liệu giả (chưa có phần cứng thật)
#define SIMULATE_DATA       0

// UUID BLE riêng cho Node Quạt (để TV1 không bị quét nhầm)
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHAR_TELEMETRY_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define CHAR_COMMAND_UUID   "1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e"

#endif