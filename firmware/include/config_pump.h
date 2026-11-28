#ifndef CONFIG_PUMP_H
#define CONFIG_PUMP_H

// Định danh thiết bị
#define DEVICE_NAME         "YOLO_PUMP_NODE"
#define DEVICE_ID           "pump"

// Chân GPIO trên Yolo UNO (Cổng Grove D5-D6 là GPIO 8 và GPIO 9)
#define PIN_RELAY           8       // Kênh 1 của Module đóng ngắt 2 kênh OhStem (cắm Máy bơm USB)
#define PIN_PUMP_CH2        9       // Kênh 2 để trống (khóa tắt an toàn khi khởi động)
#define PIN_DS18B20         1       // Giữ cùng chân GPIO 1 như Node Fan để tiện cắm chung DS18B20
#define PIN_I2C_SDA         11
#define PIN_I2C_SCL         12

// Mức kích cho Module đóng ngắt 2 kênh OhStem
// (Thường module OhStem kích mức HIGH; sẽ kiểm tra lại bằng đèn LED khi có mạch)
#define RELAY_ACTIVE_LEVEL  LOW

// Chu kỳ gửi dữ liệu BLE (miligiây)
#define TELEMETRY_INTERVAL_MS 1000

// 1 = Giả lập; 0 = Chạy phần cứng thật
#define SIMULATE_DATA       0

// UUID BLE riêng cho Node Máy Bơm (khớp 100% với gateway_pc/ble_client.py)
#define SERVICE_UUID        "5bcfa202-2fc6-469f-9fdd-d6d0d442925c"
#define CHAR_TELEMETRY_UUID "ceb6594f-47f2-4799-c8f6-fb18472c37b9"
#define CHAR_COMMAND_UUID   "2d06e6f4-e908-424b-cf4e-8b3f6e8cf98f"

#endif