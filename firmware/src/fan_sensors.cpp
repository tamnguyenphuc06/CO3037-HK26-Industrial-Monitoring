#include "config_fan.h" // Nhận chân SDA_PIN, SCL_PIN, ONE_WIRE_PIN từ TV3
#include <Wire.h>
#include <math.h>

// Các thư viện phần cứng
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <fan_sensors.h>

static bool _mock_mode = false;
static Adafruit_MPU6050 mpu;
static OneWire oneWire;
static DallasTemperature ds18b20(&oneWire);

static bool mpu_ready = false;
static bool ds_ready = false;

bool initFanSensors(bool use_mock_mode) {
    _mock_mode = use_mock_mode;
    if (_mock_mode) {
        Serial.println("[SENSOR] Dang chay che do MOCK (Du lieu gia lap)");
        return true;
    }

    // Khởi tạo I2C cho MPU6050
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    if (mpu.begin()) {
        mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
        mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);
        mpu_ready = true;
    } else {
        Serial.println("[ERROR] Khong tim thay MPU6050!");
    }

    // Khởi tạo OneWire cho DS18B20 (chế độ non-blocking conversion)
    oneWire.begin(PIN_DS18B20);
    ds18b20.begin();
    ds18b20.setWaitForConversion(false); // Không chặn CPU khi đo nhiệt
    if (ds18b20.getDeviceCount() > 0) {
        ds_ready = true;
        ds18b20.requestTemperatures();
    } else {
        Serial.println("[ERROR] Khong tim thay DS18B20!");
    }

    return (mpu_ready && ds_ready);
}

FanSensorData readFanSensors() {
    FanSensorData data;
    data.is_mock = _mock_mode;

    if (_mock_mode) {
        // Sinh dữ liệu dao động ngẫu nhiên mô phỏng quạt đang chạy
        float t = millis() / 1000.0f;
        data.ax = 0.05f * sin(2 * PI * 10 * t) + ((random(-5, 5)) / 100.0f);
        data.ay = 0.04f * cos(2 * PI * 10 * t) + ((random(-5, 5)) / 100.0f);
        data.az = 9.81f + ((random(-8, 8)) / 100.0f);
        data.gx = 0.01f; data.gy = 0.01f; data.gz = 0.02f;
        data.vibration_rms = sqrt(data.ax * data.ax + data.ay * data.ay);
        data.motor_temp = 32.5f + (random(-10, 10) / 10.0f);
        data.status = SENSOR_OK;
        return data;
    }

    // Đọc phần cứng thực tế
    data.status = SENSOR_OK;
    if (mpu_ready) {
        sensors_event_t a, g, temp;
        mpu.getEvent(&a, &g, &temp);
        data.ax = a.acceleration.x;
        data.ay = a.acceleration.y;
        data.az = a.acceleration.z;
        data.gx = g.gyro.x;
        data.gy = g.gyro.y;
        data.gz = g.gyro.z;
        data.vibration_rms = sqrt(data.ax * data.ax + data.ay * data.ay);
    } else {
        data.status = (SensorStatus)(data.status | SENSOR_ERR_MPU);
    }

    if (ds_ready) {
        data.motor_temp = ds18b20.getTempCByIndex(0);
        ds18b20.requestTemperatures(); // Bắn yêu cầu đo cho chu kỳ tiếp theo
    } else {
        data.status = (SensorStatus)(data.status | SENSOR_ERR_DS18B20);
    }

    return data;
}

void streamVibrationSampleSerial() {
    // Xuất dữ liệu dạng CSV thô qua Serial để collect_samples.py hứng
    // Định dạng: timestamp_ms,ax,ay,az
    FanSensorData d = readFanSensors();
    Serial.printf("%lu,%.4f,%.4f,%.4f\n", millis(), d.ax, d.ay, d.az);
}