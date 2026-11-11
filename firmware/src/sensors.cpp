#include "sensors.h"

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>

// Module dung chung cho FAN/PUMP. Chan GPIO den tu config cua tung node.
static uint8_t _pin_ds18b20 = 5;
static uint8_t _pin_sda = 6;
static uint8_t _pin_scl = 7;
static bool _is_simulation = true;

static Adafruit_MPU6050 mpu;
static OneWire oneWire;
static DallasTemperature ds18b20(&oneWire);

static bool mpu_ready = false;
static bool ds_ready = false;

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

    if (_is_simulation) {
        Serial.println("[SENSORS] Che do MO PHONG (SIMULATION MODE)");
        return;
    }

    Serial.println("[SENSORS] Che do DOC CAM BIEN THAT (REAL SENSORS)");

    // MPU6050: I2C, gia toc +/-4g, con quay +/-500 deg/s.
    Wire.begin(_pin_sda, _pin_scl);
    if (mpu.begin()) {
        mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
        mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);
        mpu_ready = true;
        Serial.println("[MPU6050] Khoi tao thanh cong");
    } else {
        Serial.println("[MPU6050] Khong tim thay cam bien!");
    }

    // DS18B20: yeu cau chuyen doi nhiet do khong chan loop().
    oneWire.begin(_pin_ds18b20);
    ds18b20.begin();
    ds18b20.setWaitForConversion(false);
    if (ds18b20.getDeviceCount() > 0) {
        ds_ready = true;
        ds18b20.requestTemperatures();
        Serial.println("[DS18B20] Khoi tao thanh cong");
    } else {
        Serial.println("[DS18B20] Khong tim thay cam bien!");
    }
}

SensorData sensors_read_data() {
    // Khoi tao tat ca truong = 0/false, tranh gia tri rac neu doc loi.
    SensorData data{};
    data.is_mock = _is_simulation;

    if (_is_simulation) {
        // Du lieu gia cua TV3, mo rong boi gyro va status cua TV2.
        data.temp = 29.0f + (random(0, 50) / 10.0f);
        data.ax = random(-20, 20) / 100.0f;
        data.ay = random(-20, 20) / 100.0f;
        data.az = 9.80f + (random(-15, 15) / 100.0f);
        data.gx = 0.01f;
        data.gy = 0.01f;
        data.gz = 0.02f;
        data.vibration_rms = sqrtf(data.ax * data.ax + data.ay * data.ay);
        data.status = SENSOR_OK;
        data.is_valid = true;
        return data;
    }

    bool mpu_ok = false;
    bool temperature_ok = false;

    if (mpu_ready) {
        sensors_event_t a, g, sensor_temp;
        if (mpu.getEvent(&a, &g, &sensor_temp)) {
            data.ax = a.acceleration.x;
            data.ay = a.acceleration.y;
            data.az = a.acceleration.z;
            data.gx = g.gyro.x;
            data.gy = g.gyro.y;
            data.gz = g.gyro.z;
            // Giu cach tinh tu code cu de khong mat truong du lieu.
            // Day la do lon gia toc XY tai mot thoi diem, KHONG phai RMS cua so.
            data.vibration_rms = sqrtf(data.ax * data.ax + data.ay * data.ay);
            mpu_ok = true;
        }
    }

    if (ds_ready) {
        // Doc ket qua chu ky truoc, sau do yeu cau chu ky tiep theo.
        const float measured_temp = ds18b20.getTempCByIndex(0);
        if (measured_temp != DEVICE_DISCONNECTED_C) {
            data.temp = measured_temp;
            temperature_ok = true;
        }
        ds18b20.requestTemperatures();
    }

    // Status co the bieu dien loi cua tung cam bien hoac ca hai.
    uint8_t error_flags = SENSOR_OK;
    if (!mpu_ok) error_flags |= SENSOR_ERR_MPU;
    if (!temperature_ok) error_flags |= SENSOR_ERR_DS18B20;
    data.status = static_cast<SensorStatus>(error_flags);
    data.is_valid = (data.status == SENSOR_OK);
    return data;
}

// Chi in du lieu gia toc tho cho chuong trinh collect_samples.py.
// Ham duoc khai bao nhung CHUA tu chay: can goi dinh ky tu main.cpp.
void streamVibrationSampleSerial() {
#if defined(USE_PUMP_CONFIG)
    return; // Pump hien khong thu du lieu de train TinyML.
#else
    const unsigned long timestamp_ms = millis();

    if (_is_simulation) {
        // De thu nghiem pipeline, KHONG dung cho huan luyen mo hinh thuc.
        const float t = timestamp_ms / 1000.0f;
        const float ax = 0.05f * sinf(2.0f * PI * 10.0f * t)
                       + random(-5, 5) / 100.0f;
        const float ay = 0.04f * cosf(2.0f * PI * 10.0f * t)
                       + random(-5, 5) / 100.0f;
        const float az = 9.81f + random(-8, 8) / 100.0f;
        Serial.printf("%lu,%.4f,%.4f,%.4f\n", timestamp_ms, ax, ay, az);
        return;
    }

    if (!mpu_ready) return;

    sensors_event_t a, g, sensor_temp;
    if (!mpu.getEvent(&a, &g, &sensor_temp)) return;

    Serial.printf("%lu,%.4f,%.4f,%.4f\n",
                  timestamp_ms,
                  a.acceleration.x,
                  a.acceleration.y,
                  a.acceleration.z);
#endif
}
