#ifndef CONFIG_PUMP_H
#define CONFIG_PUMP_H

// Định danh thiết bị
#define DEVICE_NAME         "YOLO_PUMP_NODE"
#define DEVICE_ID           "pump"

// Chân GPIO trên bo Yolo UNO
// Chân trên Yolo UNO của node bơm
#define PIN_RELAY           4       // GPIO4: điều khiển relay rời
#define PIN_DS18B20         5       // GPIO5 (D2): dữ liệu DS18B20
#define PIN_I2C_SDA         11      // GPIO11: SDA của cổng I2C
#define PIN_I2C_SCL         12      // GPIO12: SCL của cổng I2C

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