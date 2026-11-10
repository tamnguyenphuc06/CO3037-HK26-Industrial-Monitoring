#ifndef RELAY_H
#define RELAY_H

#include <Arduino.h>

// Khởi tạo Relay: cấu hình chân GPIO và mức kích (mặc định ngắt tải ngay lập tức)
void relay_init(uint8_t pin, uint8_t active_level);

// Đặt trạng thái Relay: true = BẬT, false = TẮT
void relay_set(bool turn_on);

// Đọc trạng thái hiện tại của Relay
bool relay_get_state();

#endif