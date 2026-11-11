#ifndef BLE_SERVICE_H
#define BLE_SERVICE_H

#include <Arduino.h>

// Khởi tạo dịch vụ BLE Server
void ble_service_init();

// Gửi bản tin Telemetry JSON lên BLE Client (PC hoặc App)
void ble_service_send_telemetry(float temp, float ax, float ay, float az, int ai_state);

// Kiểm tra xem đã có thiết bị nào kết nối vào chưa
bool ble_is_connected();

#endif