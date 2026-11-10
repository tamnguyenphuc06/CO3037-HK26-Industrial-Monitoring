#ifndef CONFIG_PUMP_H
#define CONFIG_PUMP_H

// Định danh thiết bị
#define DEVICE_NAME         "YOLO_PUMP_NODE"
#define DEVICE_ID           "pump"

// Chân GPIO trên bo Yolo UNO
#define PIN_RELAY           4       // GPIO điều khiển Relay bơm
#define PIN_DS18B20         5       // Chân One-Wire cảm biến nhiệt độ
#define PIN_I2C_SDA         6       // Chân SDA cho MPU6050
#define PIN_I2C_SCL         7       // Chân SCL cho MPU6050

// Quy ước mức kích Relay
#define RELAY_ACTIVE_LEVEL  LOW

// Chu kỳ gửi dữ liệu BLE (miligiây)
#define TELEMETRY_INTERVAL_MS 1000

// Cờ kích hoạt chế độ dữ liệu giả
#define SIMULATE_DATA       1

// UUID BLE riêng cho Node Máy Bơm
#define SERVICE_UUID        "5bcfa202-2fc6-469f-9fdd-d6d0d442925c"
#define CHAR_TELEMETRY_UUID "ceb6594f-47f2-4799-c8f6-fb18472c37b9"
#define CHAR_COMMAND_UUID   "2d06e6f4-e908-424b-cf4e-8b3f6e8cf98f"

#endif