#include <Arduino.h>
#include "relay.h"
#include "ble_service.h"
#include "sensors.h"
#include "tinyml_interface.h"

#if defined(USE_FAN_CONFIG)
    #include "config_fan.h"
#elif defined(USE_PUMP_CONFIG)
    #include "config_pump.h"
#endif

unsigned long lastTelemetryTime = 0;

void setup() {
    Serial.begin(115200);
    delay(1500);

    Serial.println("\n==========================================");
    Serial.printf(" HỆ THỐNG KHỞI ĐỘNG: %s\n", DEVICE_NAME);
    Serial.println("==========================================");

    // 1. Khởi tạo Relay an toàn
    relay_init(PIN_RELAY, RELAY_ACTIVE_LEVEL);

    // 2. Khởi tạo module Cảm biến (Dùng chung cho Quạt & Bơm)
    sensors_init(PIN_DS18B20, PIN_I2C_SDA, PIN_I2C_SCL, SIMULATE_DATA);

    // 3. Khởi tạo TinyML (Tự động bật với Quạt, bỏ qua với Bơm)
    tinyml_init();

    // 4. Khởi tạo dịch vụ BLE
    ble_service_init();
}

void loop() {
    unsigned long currentMillis = millis();

    // Định kỳ đọc cảm biến và gửi Telemetry mỗi 1000ms
    if (currentMillis - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryTime = currentMillis;

        // Đọc dữ liệu (tự động theo chế độ SIMULATE_DATA trong config)
        SensorData sensor_data = sensors_read_data();

        // Chạy TinyML (nếu là Node Quạt)
        int ai_state = tinyml_infer(sensor_data);

        // Bắn dữ liệu qua BLE
        ble_service_send_telemetry(
            sensor_data.temp, 
            sensor_data.ax, 
            sensor_data.ay, 
            sensor_data.az, 
            ai_state
        );
    }
}