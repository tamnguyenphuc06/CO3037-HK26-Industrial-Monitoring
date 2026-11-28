
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
    #error "Phai khai bao USE_FAN_CONFIG hoac USE_PUMP_CONFIG"
#endif

// 1: FAN xuat CSV de thu du lieu huan luyen.
// 0: FAN chay TinyML va BLE.
// PUMP khong bi anh huong boi che do nay.
#ifndef FAN_SAMPLE_MODE
#define FAN_SAMPLE_MODE 0
#endif

static constexpr unsigned long SAMPLE_INTERVAL_MS = 20;
static unsigned long lastSampleTime = 0;
static unsigned long lastTelemetryTime = 0;

#if defined(USE_FAN_CONFIG)

// PWM 8-bit: 0-255.
// 130: thu nghiem fan_low_speed.
// 255: thu nghiem fan_normal.

#if FAN_SAMPLE_MODE
static uint8_t fanPwmDuty = 220;
static bool fanProtectionLocked = false;
#else
static uint8_t fanPwmDuty = 0;
static bool fanProtectionLocked = true;
#endif

void fan_set_pwm(uint8_t duty) {
    // Khong cho FAN chay khi dang bi khoa
    if (fanProtectionLocked && duty > 0) {
        Serial.println("[FAN] PWM rejected: Protection LOCKED");
        return;
    }

    if (ledcWrite(PIN_FAN_D3, duty)) {
        fanPwmDuty = duty;
        Serial.printf("[FAN] PWM updated: %u/255\n",
                      (unsigned)fanPwmDuty);
    } else {
        Serial.println("[FAN] Failed to update PWM");
    }
}

bool fan_protection_lock() {
    fanProtectionLocked = true;

    if (!ledcWrite(PIN_FAN_D3, 0)) {
        Serial.println("[FAN] LOCK FAILED");
        return false;
    }

    fanPwmDuty = 0;
    Serial.println("[FAN] PROTECTION LOCKED");
    return true;
}

bool fan_protection_reset() {
    if (!fanProtectionLocked) {
        Serial.println("[FAN] Already unlocked");
        return false;
    }

    // Dam bao PWM = 0 truoc khi mo khoa
    if (!ledcWrite(PIN_FAN_D3, 0)) {
        Serial.println("[FAN] RESET FAILED");
        return false;
    }

    fanPwmDuty = 0;
    fanProtectionLocked = false;

    Serial.println("[FAN] PROTECTION UNLOCKED");
    return true;
}

bool fan_protection_is_locked() {
    return fanProtectionLocked;
}

// Luu du lieu FAN moi nhat de gui BLE.
static SensorData latestFanData{};
static bool hasFanData = false;

#endif

void setup() {
    Serial.begin(115200);
    delay(1500);

    // Relay o trang thai TAT khi khoi dong.
    relay_init(PIN_RELAY, RELAY_ACTIVE_LEVEL);

#if defined(USE_FAN_CONFIG)

    // Dieu khien quat OhStem bang D3-D4.
    pinMode(PIN_FAN_D4, OUTPUT);
    digitalWrite(PIN_FAN_D4, LOW);

    pinMode(PIN_FAN_D3, OUTPUT);
    digitalWrite(PIN_FAN_D3, LOW);

    // PWM 1000 Hz, 8-bit.
    bool pwmReady = ledcAttach(PIN_FAN_D3, 1000, 8);

    if (pwmReady) {
        ledcWrite(PIN_FAN_D3, fanPwmDuty);

        Serial.printf(
            "[FAN] PWM = %u/255\n",
            (unsigned)fanPwmDuty
        );
    } else {
        digitalWrite(PIN_FAN_D3, LOW);
        Serial.println("[FAN] Loi khoi tao PWM!");
    }

#elif defined(USE_PUMP_CONFIG)

    // Khoa kenh 2 cua Module dong ngat 2 kenh OhStem o trang thai TAT an toan
    uint8_t ch2_inactive = (RELAY_ACTIVE_LEVEL == HIGH) ? LOW : HIGH;
    digitalWrite(PIN_PUMP_CH2, ch2_inactive);
    pinMode(PIN_PUMP_CH2, OUTPUT);
    digitalWrite(PIN_PUMP_CH2, ch2_inactive);

#endif

#if defined(USE_FAN_CONFIG) && FAN_SAMPLE_MODE

    // Che do thu CSV, khong chay BLE/TinyML.
    Serial.println("[FAN] SAMPLE MODE");

    sensors_init(
        PIN_DS18B20,
        PIN_I2C_SDA,
        PIN_I2C_SCL,
        SIMULATE_DATA
    );

    lastSampleTime = millis();
    return;

#else

    // Che do van hanh binh thuong.
    Serial.println("\n================================");
    Serial.printf("DEVICE: %s\n", DEVICE_NAME);
    Serial.println("================================");

    sensors_init(
        PIN_DS18B20,
        PIN_I2C_SDA,
        PIN_I2C_SCL,
        SIMULATE_DATA
    );

#if defined(USE_FAN_CONFIG)
    tinyml_init();
#endif

    ble_service_init();

    lastSampleTime = millis();
    lastTelemetryTime = millis();

    Serial.println("[SYSTEM] Khoi tao hoan tat.");

#endif
}

void loop() {

#if defined(USE_FAN_CONFIG) && FAN_SAMPLE_MODE

    // FAN: chi thu du lieu gia toc de train.
    const unsigned long now = millis();

    if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
        lastSampleTime = now;
        streamVibrationSampleSerial();
    }

#elif defined(USE_FAN_CONFIG)

    // FAN: doc MPU6500 moi ~20 ms.
    const unsigned long now = millis();

    if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
        lastSampleTime = now;

        latestFanData = sensors_read_data();
        hasFanData = true;

        // Them mot bo ax, ay, az vao bo dem.
        // Ham tu chay inference khi du 100 mau,
        // sau do moi 50 mau moi.
        tinyml_infer(latestFanData);
    }

    // FAN: gui BLE moi 1000 ms.
    if (now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryTime = now;

        if (hasFanData) {
            // Lay ket qua AI moi nhat, khong suy luan lai.
            int ai_state = tinyml_get_state();

ble_service_send_telemetry(
    latestFanData.temp,
    latestFanData.ax,
    latestFanData.ay,
    latestFanData.az,
    ai_state,
    fanPwmDuty
);
        }
    }

#elif defined(USE_PUMP_CONFIG)

    // PUMP: giu chu ky doc va gui BLE 1 giay.
    // Khong chay mo hinh TinyML cua FAN.
    const unsigned long now = millis();

    if (now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryTime = now;

        SensorData sensor_data = sensors_read_data();

        ble_service_send_telemetry(
            sensor_data.temp,
            sensor_data.ax,
            sensor_data.ay,
            sensor_data.az,
            -1
        );
    }

#endif
}
