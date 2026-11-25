#ifndef TINYML_INTERFACE_H
#define TINYML_INTERFACE_H

#include "sensors.h"

// Ma trang thai gui qua BLE:
// -1: chua du mau / khong chac chan / doc cam bien loi
//  0: fan_idle
//  1: fan_low_speed
//  2: fan_normal
void tinyml_init();

// PHẢI goi moi ~20 ms tren FAN; moi lan cung cap mot bo (ax,ay,az).
// Tu dong suy luan khi du 100 mau va sau moi 50 mau moi.
// Tra ve trang thai du doan moi nhat; -1 neu chua co du doan tin cay.
int tinyml_infer(const SensorData& data);

// Doc lai ket qua moi nhat (khong chay suy luan lai).
int tinyml_get_state();
float tinyml_get_confidence();

#endif // TINYML_INTERFACE_H
