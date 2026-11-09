#include "tinyml_interface.h"

#if defined(USE_FAN_CONFIG)
// Chỉ Node Quạt mới cần khởi tạo và chạy TinyML
void tinyml_init() {
    Serial.println("[TINYML] Khởi tạo mô hình AI phát hiện rung bất thường cho QUẠT...");
    // TODO (TV2): Khởi tạo mô hình Edge Impulse đã export ở đây
}

int tinyml_infer(const SensorData& data) {
    // TODO (TV2): Nạp mẫu ax, ay, az vào tensor và chạy invoke()
    // Tạm thời trả về 0 (Normal) trong chế độ test
    return 0; 
}

#else
// Node Máy Bơm không chạy TinyML -> hàm rỗng tiết kiệm tài nguyên
void tinyml_init() {}
int tinyml_infer(const SensorData& data) { return 0; }
#endif