#ifndef SENSORS_H
#define SENSORS_H

#include <Arduino.h>

// Ma loi cam bien. Moi bit dai dien cho mot cam bien bi loi.
enum SensorStatus : uint8_t {
    SENSOR_OK          = 0,
    SENSOR_ERR_MPU     = 1,
    SENSOR_ERR_DS18B20 = 2,
    SENSOR_ERR_ALL     = 3
};

// Du lieu dung chung cho node FAN va node PUMP.
// Giu nguyen cac truong TV3 da dung: temp, ax, ay, az, is_valid.
struct SensorData {
    float temp;            // DS18B20, do C
    float ax, ay, az;      // MPU6050, gia toc m/s^2
    bool is_valid;         // true khi CA HAI cam bien deu doc thanh cong

    // Thong tin bo sung tu fan_sensors.h cua TV2:
    float gx, gy, gz;      // MPU6050, van toc goc rad/s
    float vibration_rms;   // Ten truong cu: hien tai chi la do lon gia toc XY tuc thoi,
                           // CHUA phai RMS tren cua so thoi gian
    SensorStatus status;   // Bit 0: MPU loi; bit 1: DS18B20 loi
    bool is_mock;          // true = du lieu gia lap, khong phai du lieu thuc
};

void sensors_init(uint8_t pin_ds18b20,
                  uint8_t pin_sda,
                  uint8_t pin_scl,
                  bool is_simulation);

SensorData sensors_read_data();

// Moi lan goi in mot dong CSV: timestamp_ms,ax,ay,az.
// Can goi moi 20 ms tu main.cpp de co luong ~50 Hz (chua duoc tich hop vao main.cpp).
// Chi node FAN su dung de thu du lieu TinyML.
void streamVibrationSampleSerial();

#endif // SENSORS_H
