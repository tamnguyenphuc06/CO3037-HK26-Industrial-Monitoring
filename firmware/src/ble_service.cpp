#include "ble_service.h"
#include "relay.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <ArduinoJson.h>

#if defined(USE_FAN_CONFIG)
void fan_set_pwm(uint8_t duty);
bool fan_protection_lock();
bool fan_protection_reset();
bool fan_protection_is_locked();
#endif

#if defined(USE_FAN_CONFIG)
    #include "config_fan.h"
#elif defined(USE_PUMP_CONFIG)
    #include "config_pump.h"
#endif

static BLEServer* pServer = nullptr;
static BLECharacteristic* pTelemetryChar = nullptr;
static BLECharacteristic* pCommandChar = nullptr;
static bool oldDeviceConnected = false;

// Callback quản lý kết nối
class ServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) override {
        Serial.println("\n[BLE] >>> Client da KET NOI thanh cong! <<<");
    }

    void onDisconnect(BLEServer* pServer) override {
        Serial.println("\n[BLE] >>> Client da NGAT KET NOI! Dang quang ba lai... <<<");
        pServer->startAdvertising(); // Quảng bá lại
    }
};

// Callback nhận lệnh RPC từ Client gửi xuống
class CommandCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) override {
        String rxValue = pCharacteristic->getValue();
        if (rxValue.length() > 0) {
            Serial.printf("\n[BLE RX Nhan lenh]: %s\n", rxValue.c_str());

            JsonDocument doc;
            DeserializationError error = deserializeJson(doc, rxValue);

            if (!error) {
                const char* cmd = doc["cmd"] | "";
                if (strcmp(cmd, "RELAY_ON") == 0) {
                    relay_set(true);
                    Serial.println("-> [KET QUA]: DA BAT RELAY!");
                } else if (strcmp(cmd, "RELAY_OFF") == 0) {
    relay_set(false);
    Serial.println("-> [KET QUA]: DA TAT RELAY!");
  }
     #if defined(USE_FAN_CONFIG)
      else if (strcmp(cmd, "SET_FAN_PWM") == 0) {
    if (!doc["value"].is<int>()) {
        Serial.println("[FAN] Invalid PWM type");
    } else {
        int pwm = doc["value"].as<int>();

        if (pwm >= 0 && pwm <= 255) {
            fan_set_pwm(static_cast<uint8_t>(pwm));
        } else {
            Serial.println("[FAN] PWM out of range");
        }
    }
}     
else if (strcmp(cmd, "FAN_PROTECTION_LOCK") == 0) {
    bool success = fan_protection_lock();

    Serial.printf("[BLE] FAN LOCK: %s\n",
                  success ? "SUCCESS" : "FAILED");
}
else if (strcmp(cmd, "FAN_PROTECTION_RESET") == 0) {
    bool success = fan_protection_reset();

    Serial.printf("[BLE] FAN RESET: %s\n",
                  success ? "SUCCESS" : "FAILED");
}

        #endif
            } else {
                if (rxValue == "ON" || rxValue == "1") {
                    relay_set(true);
                    Serial.println("-> [KET QUA]: DA BAT RELAY (chuoi tho)!");
                } else if (rxValue == "OFF" || rxValue == "0") {
                    relay_set(false);
                    Serial.println("-> [KET QUA]: DA TAT RELAY (chuoi tho)!");
                }
            }
        }
    }
};

void ble_service_init() {
    Serial.printf("[BLE] Khoi tao Bluetooth ten: %s\n", DEVICE_NAME);
    BLEDevice::init(DEVICE_NAME);

    // THÊM DÒNG NÀY: Cho phép truyền các bản tin dài lên đến 512 bytes
    BLEDevice::setMTU(512);

    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());

    // Tạo Service
    BLEService *pService = pServer->createService(SERVICE_UUID);

    // 1. Telemetry Characteristic
    pTelemetryChar = pService->createCharacteristic(
        CHAR_TELEMETRY_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );

    // 2. Command Characteristic
    pCommandChar = pService->createCharacteristic(
        CHAR_COMMAND_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );
    pCommandChar->setCallbacks(new CommandCallbacks());

    pService->start();

    // Quảng bá thiết bị
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06);
    BLEDevice::startAdvertising();
    Serial.println("[BLE] Dang phat quang ba, san sang ket noi...");
}

void ble_service_send_telemetry(
    float temp, float ax, float ay, float az,
    int ai_state, int pwm
) {
    if (pServer == nullptr || pTelemetryChar == nullptr) return;

    // Kiểm tra trực tiếp số lượng client kết nối từ server
    bool isConnected = (pServer->getConnectedCount() > 0);

    // Theo dõi trạng thái để in log
    if (isConnected && !oldDeviceConnected) {
        oldDeviceConnected = true;
    }
    if (!isConnected && oldDeviceConnected) {
        oldDeviceConnected = false;
        pServer->startAdvertising();
    }

    if (!isConnected) return;

    // Đóng gói JSON
    JsonDocument doc;
    doc["id"] = DEVICE_ID;
    doc["temp"] = serialized(String(temp, 1));
    doc["ax"] = serialized(String(ax, 2));
    doc["ay"] = serialized(String(ay, 2));
    doc["az"] = serialized(String(az, 2));
    doc["relay"] = relay_get_state() ? 1 : 0;
    doc["ai"] = ai_state;
    
    if (pwm >= 0 && pwm <= 255) {
    doc["pwm"] = pwm;
}

#if defined(USE_FAN_CONFIG)
doc["protection_locked"] = fan_protection_is_locked();
#endif

    
char payload[224];

if (measureJson(doc) >= sizeof(payload)) {
    Serial.println("[BLE] Telemetry too large");
    return;
}

serializeJson(doc, payload, sizeof(payload));


    pTelemetryChar->setValue((uint8_t*)payload, strlen(payload));
    pTelemetryChar->notify();

    Serial.printf("[BLE TX]: %s\n", payload);
}

bool ble_is_connected() {
    return (pServer != nullptr && pServer->getConnectedCount() > 0);
}