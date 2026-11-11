#include <Arduino.h>
#include "relay.h"
#include "ble_service.h"
#include "sensors.h"
#include "tinyml_interface.h"

#if defined(USE_FAN_CONFIG)
    #include "config_fan.h"
#elif defined(USE_PUMP_CONFIG)
    #include "config_pump.h"
#else
    #error "Phai khai bao USE_FAN_CONFIG hoac USE_PUMP_CONFIG trong platformio.ini"
#endif

// 1: FAN xuat CSV qua USB Serial de collect_samples.py thu mau.
// 0: FAN hoat dong binh thuong (TinyML/BLE/relay).
// PUMP luon chay che do binh thuong, khong phu thuoc co nay.
#ifndef FAN_SAMPLE_MODE
#define FAN_SAMPLE_MODE 0
#endif

static constexpr unsigned long SAMPLE_INTERVAL_MS = 20; // ~50 Hz
static unsigned long lastSampleTime = 0;
static unsigned long lastTelemetryTime = 0;

void setup() {
    Serial.begin(115200);
    delay(1500);

    // Dat relay ve trang thai TAT ngay khi khoi dong (ca che do thu mau).
    relay_init(PIN_RELAY, RELAY_ACTIVE_LEVEL);

#if defined(USE_FAN_CONFIG) && FAN_SAMPLE_MODE
    // Chi khoi tao cam bien, khong khoi dong BLE/TinyML khi thu mau.
    // SIMULATE_DATA=1: mau gia de test pipeline Python.
    // SIMULATE_DATA=0: doc MPU6050 that de tao dataset.
    sensors_init(PIN_DS18B20, PIN_I2C_SDA, PIN_I2C_SCL, SIMULATE_DATA);
    lastSampleTime = millis();
    return;
#else
    // Che do van hanh binh thuong cua TV3: FAN (khi tat sample) / PUMP.
    Serial.println("\n==========================================");
    Serial.printf(" HE THONG KHOI DONG: %s\n", DEVICE_NAME);
    Serial.println("==========================================");

    sensors_init(PIN_DS18B20, PIN_I2C_SDA, PIN_I2C_SCL, SIMULATE_DATA);
    tinyml_init();
    ble_service_init();
#endif
}

void loop() {
#if defined(USE_FAN_CONFIG) && FAN_SAMPLE_MODE
    // 1 dong CSV / ~20 ms: timestamp_ms,ax,ay,az.
    // collect_samples.py doc tren cung cong COM; KHONG mo Serial Monitor dong thoi.
    const unsigned long now = millis();
    if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
        lastSampleTime = now;
        streamVibrationSampleSerial();
    }
#else
    const unsigned long currentMillis = millis();

    // Telemetry BLE theo chu ky 1 giay nhu main.cpp goc cua TV3.
    if (currentMillis - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryTime = currentMillis;

        SensorData sensor_data = sensors_read_data();
        int ai_state = tinyml_infer(sensor_data);

        ble_service_send_telemetry(
            sensor_data.temp,
            sensor_data.ax,
            sensor_data.ay,
            sensor_data.az,
            ai_state
        );
    }
#endif
}
