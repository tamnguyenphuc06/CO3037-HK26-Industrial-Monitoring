#ifndef TINYML_INTERFACE_H
#define TINYML_INTERFACE_H

#include "sensors.h"

// Khởi tạo TinyML
void tinyml_init();

// Chạy suy luận từ dữ liệu rung: trả về 0 (Bình thường) hoặc 1 (Bất thường/Lệch trục)
int tinyml_infer(const SensorData& data);

#endif