#include "relay.h"

static uint8_t _relay_pin = 4;
static uint8_t _active_level = LOW;
static bool _current_state = false; // false = OFF, true = ON

void relay_init(uint8_t pin, uint8_t active_level) {
    _relay_pin = pin;
    _active_level = active_level;
    _current_state = false;

    // Ngắt tải trước khi chuyển sang OUTPUT để chống chớp giật rơ-le khi khởi động
    uint8_t inactive_level = (_active_level == HIGH) ? LOW : HIGH;
    digitalWrite(_relay_pin, inactive_level);
    pinMode(_relay_pin, OUTPUT);
    digitalWrite(_relay_pin, inactive_level);
}

void relay_set(bool turn_on) {
    _current_state = turn_on;
    if (_current_state) {
        digitalWrite(_relay_pin, _active_level);
    } else {
        uint8_t inactive_level = (_active_level == HIGH) ? LOW : HIGH;
        digitalWrite(_relay_pin, inactive_level);
    }
}

bool relay_get_state() {
    return _current_state;
}