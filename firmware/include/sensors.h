#ifndef SENSORS_H
#define SENSORS_H

#include <Arduino.h>

// Struct chứa toàn bộ dữ liệu cảm biến đọc được
struct SensorData {
    float temp;     // Nhiệt độ DS18B20 (°C)
    float ax;       // Gia tốc X MPU6050 (m/s2 hoặc g)
    float ay;       // Gia tốc Y MPU6050 (m/s2 hoặc g)
    float az;       // Gia tốc Z MPU6050 (m/s2 hoặc g)
    bool is_valid;  // Trạng thái đọc cảm biến (true: OK, false: lỗi cảm biến)
};

// Khởi tạo cảm biến với chân GPIO và chế độ cấu hình
void sensors_init(uint8_t pin_ds18b20, uint8_t pin_sda, uint8_t pin_scl, bool is_simulation);

// Đọc dữ liệu (tự động chuyển giữa dữ liệu giả và đọc phần cứng thật)
SensorData sensors_read_data();

#endif