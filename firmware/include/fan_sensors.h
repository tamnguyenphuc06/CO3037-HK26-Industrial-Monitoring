#ifndef FAN_SENSORS_H
#define FAN_SENSORS_H

#include <Arduino.h>

// Trạng thái vận hành của cảm biến
enum SensorStatus {
    SENSOR_OK = 0,
    SENSOR_ERR_MPU = 1,
    SENSOR_ERR_DS18B20 = 2,
    SENSOR_ERR_ALL = 3
};

// Cấu trúc dữ liệu chứa toàn bộ thông số đo
struct FanSensorData {
    float ax, ay, az;         // Gia tốc 3 trục (đơn vị: m/s^2 hoặc g)
    float gx, gy, gz;         // Vận tốc góc 3 trục (đơn vị: rad/s hoặc deg/s)
    float vibration_rms;      // Giá trị độ rung hiệu dụng tính nhanh
    float motor_temp;         // Nhiệt độ tiếp xúc thân motor từ DS18B20 (°C)
    SensorStatus status;      // Trạng thái phần cứng
    bool is_mock;             // Cờ đánh dấu dữ liệu giả hay thật
};

// Khởi tạo các bus giao tiếp và cảm biến
bool initFanSensors(bool use_mock_mode = false);

// Đọc dữ liệu định kỳ cho chu kỳ telemetry (bất đồng bộ, không nghẽn loop)
FanSensorData readFanSensors();

// Chế độ in luồng dữ liệu thô tốc độ cao qua Serial phục vụ công cụ collect_samples.py
void streamVibrationSampleSerial();

#endif // FAN_SENSORS_H