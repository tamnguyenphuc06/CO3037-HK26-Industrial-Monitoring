#include <Arduino.h>
#include "relay.h"
#include "ble_service.h"

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

    // 2. Khởi tạo dịch vụ BLE
    ble_service_init();
}

void loop() {
    unsigned long currentMillis = millis();

    // Định kỳ gửi Telemetry mỗi 1000ms
    if (currentMillis - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryTime = currentMillis;

#if SIMULATE_DATA
        // Giả lập dữ liệu cảm biến:
        float simulated_temp = 29.0 + (random(0, 50) / 10.0);       // Nhiệt độ ~29.0 - 34.0 °C
        float simulated_ax = (random(-20, 20) / 100.0);              // Gia tốc X quanh 0
        float simulated_ay = (random(-20, 20) / 100.0);              // Gia tốc Y quanh 0
        float simulated_az = 9.80 + (random(-15, 15) / 100.0);       // Trọng lực Z ~9.8 m/s2
        int simulated_ai_state = 0;                                  // 0: Bình thường
#else
        // Chỗ này về sau sẽ gọi hàm đọc cảm biến thật của TV2
        float simulated_temp = 0.0;
        float simulated_ax = 0.0, simulated_ay = 0.0, simulated_az = 0.0;
        int simulated_ai_state = 0;
#endif

        // Gửi qua BLE nếu có Client kết nối
        ble_service_send_telemetry(simulated_temp, simulated_ax, simulated_ay, simulated_az, simulated_ai_state);
    }
}