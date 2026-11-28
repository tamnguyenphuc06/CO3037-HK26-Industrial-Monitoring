#include "sensors.h"

#include <Wire.h>
#include <MPU6500_WE.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>

// Chan se duoc cap nhat tu config_fan.h / config_pump.h.
static uint8_t _pin_ds18b20 = 5;
static uint8_t _pin_sda = 11;
static uint8_t _pin_scl = 12;
static bool _is_simulation = true;

// Dia chi I2C da kiem tra tren module cua ban.
static constexpr uint8_t MPU_ADDRESS = 0x68;

// Quy doi don vi ve dung quy uoc cua du an.
static constexpr float GRAVITY_MS2 = 9.80665f;
static constexpr float DEG_TO_RAD_FACTOR = PI / 180.0f;

static MPU6500_WE mpu(MPU_ADDRESS);
static OneWire oneWire;
static DallasTemperature ds18b20(&oneWire);

static bool mpu_ready = false;
static bool ds_ready = false;

static constexpr unsigned long DS18B20_INTERVAL_MS = 800;
static constexpr unsigned long DS18B20_RETRY_MS    = 2000;
static unsigned long last_ds_request_ms = 0;
static unsigned long last_ds_retry_ms   = 0;
static float last_ds_temp = 0.0f;
static bool ds_has_valid_temp = false;

// Kiem tra module con tra loi tren I2C.
static bool mpuResponds() {
    Wire.beginTransmission(MPU_ADDRESS);
    return Wire.endTransmission() == 0;
}

// Doc gia toc, doi tu g sang m/s^2.
static bool readAcceleration(float &ax, float &ay, float &az) {
    if (!mpu_ready || !mpuResponds()) {
        return false;
    }

    xyzFloat acceleration = mpu.getGValues();

    ax = acceleration.x * GRAVITY_MS2;
    ay = acceleration.y * GRAVITY_MS2;
    az = acceleration.z * GRAVITY_MS2;

    return isfinite(ax) && isfinite(ay) && isfinite(az);
}

// In loi dinh ky de khong bo lo khi mo Serial Monitor muon.
static void printMpuError() {
    static unsigned long lastErrorTime = 0;
    const unsigned long now = millis();

    if (now - lastErrorTime >= 2000) {
        lastErrorTime = now;
        Serial.println("[LOI] MPU6500 chua san sang hoac doc that bai.");
    }
}

void sensors_init(uint8_t pin_ds18b20,
                  uint8_t pin_sda,
                  uint8_t pin_scl,
                  bool is_simulation) {
    _pin_ds18b20 = pin_ds18b20;
    _pin_sda = pin_sda;
    _pin_scl = pin_scl;
    _is_simulation = is_simulation;

    mpu_ready = false;
    ds_ready = false;
    ds_has_valid_temp = false;
    last_ds_temp = 0.0f;
    last_ds_request_ms = 0;
    last_ds_retry_ms = 0;

    if (_is_simulation) {
        Serial.println("[SENSORS] Che do MO PHONG");
        return;
    }

    Serial.println("[SENSORS] Che do DOC CAM BIEN THAT");

    // Khoi tao I2C theo chan cau hinh cua node.
    Wire.begin(_pin_sda, _pin_scl);
    Wire.setClock(100000);
    delay(100);

    // Khoi tao MPU6500.
    if (mpu.init()) {
        // Gia toc +/-4g, van toc goc +/-500 do/giay.
        mpu.setAccRange(MPU6500_ACC_RANGE_4G);
        mpu.setGyrRange(MPU6500_GYRO_RANGE_500);

        // Bat bo loc thong thap cho gia toc va con quay.
        mpu.enableAccDLPF(true);
        mpu.setAccDLPF(MPU6500_DLPF_4);

        mpu.enableGyrDLPF();
        mpu.setGyrDLPF(MPU6500_DLPF_4);

        // Tan so noi bo: 1000 / (1 + 19) = 50 Hz.
        mpu.setSampleRateDivider(19);

        delay(100);
        mpu_ready = true;

        Serial.println("[MPU6500] Khoi tao thanh cong tai 0x68");
    } else {
        Serial.println("[MPU6500] Khoi tao that bai!");
    }

    // Khoi tao DS18B20 tren duong OneWire rieng.
    oneWire.begin(_pin_ds18b20);
    ds18b20.begin();
    ds18b20.setResolution(12);
    ds18b20.setWaitForConversion(false);

    if (ds18b20.getDeviceCount() > 0) {
        ds_ready = true;
        ds18b20.requestTemperatures();
        last_ds_request_ms = millis();
        Serial.printf("[DS18B20] Khoi tao thanh cong tren GPIO %u\n", _pin_ds18b20);
    } else {
        last_ds_retry_ms = millis();
        Serial.printf("[DS18B20] Khong tim thay cam bien tren GPIO %u!\n", _pin_ds18b20);
    }
}

SensorData sensors_read_data() {
    SensorData data{};
    data.is_mock = _is_simulation;

    if (_is_simulation) {
        data.temp = 29.0f + random(0, 50) / 10.0f;

        data.ax = random(-20, 20) / 100.0f;
        data.ay = random(-20, 20) / 100.0f;
        data.az = 9.80f + random(-15, 15) / 100.0f;

        data.gx = 0.01f;
        data.gy = 0.01f;
        data.gz = 0.02f;

        data.vibration_rms =
            sqrtf(data.ax * data.ax + data.ay * data.ay);

        data.status = SENSOR_OK;
        data.is_valid = true;
        return data;
    }

    bool mpu_ok = readAcceleration(data.ax, data.ay, data.az);
    bool temperature_ok = false;

    if (mpu_ok) {
        xyzFloat gyro = mpu.getGyrValues();

        // Thu vien tra do/giay; du an dung rad/giay.
        data.gx = gyro.x * DEG_TO_RAD_FACTOR;
        data.gy = gyro.y * DEG_TO_RAD_FACTOR;
        data.gz = gyro.z * DEG_TO_RAD_FACTOR;

        mpu_ok = isfinite(data.gx)
              && isfinite(data.gy)
              && isfinite(data.gz);

        // Giu truong cu: do lon gia toc XY tuc thoi.
        // Day chua phai RMS tren mot cua so mau.
        data.vibration_rms =
            sqrtf(data.ax * data.ax + data.ay * data.ay);
    }

    const unsigned long now = millis();
    if (!ds_ready) {
        // Tu dong do lai moi 2 giay neu luc khoi dong cam long hoac bi rut day
        if (now - last_ds_retry_ms >= DS18B20_RETRY_MS) {
            last_ds_retry_ms = now;
            ds18b20.begin();
            if (ds18b20.getDeviceCount() > 0) {
                ds18b20.setResolution(12);
                ds18b20.setWaitForConversion(false);
                ds18b20.requestTemperatures();
                last_ds_request_ms = now;
                ds_ready = true;
                Serial.println("[DS18B20] Da ket noi lai cam bien!");
            }
        }
    } else if (now - last_ds_request_ms >= DS18B20_INTERVAL_MS) {
        const float temperature = ds18b20.getTempCByIndex(0);
        if (temperature != DEVICE_DISCONNECTED_C && isfinite(temperature)) {
            last_ds_temp = temperature;
            ds_has_valid_temp = true;
        } else {
            ds_has_valid_temp = false;
            ds_ready = false;
            last_ds_retry_ms = now;
            Serial.println("[DS18B20] Loi: Mat ket noi cam bien (-127 C)!");
        }
        if (ds_ready) {
            ds18b20.requestTemperatures();
            last_ds_request_ms = now;
        }
    }
    if (ds_has_valid_temp) {
        data.temp = last_ds_temp;
        temperature_ok = true;
    }

    uint8_t error_flags = SENSOR_OK;

    if (!mpu_ok) {
        error_flags |= SENSOR_ERR_MPU;
    }

    if (!temperature_ok) {
        error_flags |= SENSOR_ERR_DS18B20;
    }

    data.status = static_cast<SensorStatus>(error_flags);
    data.is_valid = (data.status == SENSOR_OK);

    return data;
}

void streamVibrationSampleSerial() {
#if defined(USE_PUMP_CONFIG)
    return;
#else
    const unsigned long timestamp_ms = millis();

    if (_is_simulation) {
        const float t = timestamp_ms / 1000.0f;

        const float ax =
            0.05f * sinf(2.0f * PI * 10.0f * t)
            + random(-5, 5) / 100.0f;

        const float ay =
            0.04f * cosf(2.0f * PI * 10.0f * t)
            + random(-5, 5) / 100.0f;

        const float az =
            9.81f + random(-8, 8) / 100.0f;

        Serial.printf("%lu,%.4f,%.4f,%.4f\n",
                      timestamp_ms, ax, ay, az);
        return;
    }

    float ax, ay, az;

    if (!readAcceleration(ax, ay, az)) {
        printMpuError();
        return;
    }

    // Chi xuat gia toc MPU6500, khong phu thuoc DS18B20.
    Serial.printf("%lu,%.4f,%.4f,%.4f\n",
                  timestamp_ms, ax, ay, az);
#endif
}