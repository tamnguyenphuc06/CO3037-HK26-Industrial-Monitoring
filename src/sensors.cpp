#include "sensors.h"

static uint8_t _pin_ds18b20 = 5;
static uint8_t _pin_sda = 6;
static uint8_t _pin_scl = 7;
static bool _is_simulation = true;

void sensors_init(uint8_t pin_ds18b20, uint8_t pin_sda, uint8_t pin_scl, bool is_simulation) {
    _pin_ds18b20 = pin_ds18b20;
    _pin_sda = pin_sda;
    _pin_scl = pin_scl;
    _is_simulation = is_simulation;

    if (_is_simulation) {
        Serial.println("[SENSORS] Chế độ: GIẢ LẬP DỮ LIỆU (SIMULATION MODE)");
    } else {
        Serial.println("[SENSORS] Chế độ: ĐỌC PHẦN CỨNG THẬT (REAL SENSORS)");
        // TODO (TV2): Khởi tạo I2C Wire cho MPU6050 và OneWire cho DS18B20 ở đây
    }
}

SensorData sensors_read_data() {
    SensorData data;

    if (_is_simulation) {
        // Sinh dữ liệu giả lập thực tế
        data.temp = 29.0 + (random(0, 50) / 10.0);
        data.ax = (random(-20, 20) / 100.0);
        data.ay = (random(-20, 20) / 100.0);
        data.az = 9.80 + (random(-15, 15) / 100.0);
        data.is_valid = true;
    } else {
        // TODO (TV2): Ghép hàm đọc thực tế của TV2 vào đây
        // data.temp = ds18b20_get_temp();
        // mpu6050_get_accel(&data.ax, &data.ay, &data.az);
        data.temp = 0.0;
        data.ax = 0.0; data.ay = 0.0; data.az = 0.0;
        data.is_valid = false;
    }

    return data;
}