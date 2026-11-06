# Industrial IoT Monitoring & Predictive Maintenance (CO3037)

Course Project for **Internet of Things (CO3037)** – Semester 261 (2025–2026), Ho Chi Minh City University of Technology (HCMUT).

* **Instructor:** Dr. Le Trong Nhan

## 1. Overview

An end-to-end 3-tier Industrial IoT system monitoring two simulated industrial assets:

* **Board 1 (Environment Node):** Ambient temperature and humidity tracking via Tasmota (`DHT20`).
* **Board 2 (M1 - Ventilation Fan):** Vibration (`MPU6050`), temperature (`DS18B20`), local webserver, relay control, and on-device TinyML anomaly detection.
* **Board 3 (M2 - Water Pump):** Vibration (`MPU6050`), temperature (`DS18B20`), local webserver, and relay control.

## 2. Team Members

| No. | Full Name | Student ID | GitHub | Role |
| :--- | :--- | :--- | :--- | :--- |
| 1 | [Member 1] | [ID 1] | `@user1` | Board 1 (Tasmota), Board 2 (Fan + TinyML), Report |
| 2 | [Member 2] | [ID 2] | `@user2` | Board 3 (Pump), BLE & Local Webserver |
| 3 | [Member 3] | [ID 3] | `@user3` | Local Python Gateway, Gateway AI, CoreIOT Cloud |

## 3. System Architecture

```text
====================================================================================================
                          TIER 1: FIELD DEVICES & SENSORS (3x ESP32-S3)
====================================================================================================

  +-------------------------+       +----------------------------+       +-------------------------+
  |   BOARD 1: ENVIRONMENT  |       |      BOARD 2: FAN NODE     |       |   BOARD 3: PUMP NODE    |
  |   (Tasmota Firmware)    |       |     (C++ / Arduino Code)   |       |   (C++ / Arduino Code)  |
  +-------------------------+       +----------------------------+       +-------------------------+
  | - Sensor: DHT20 (I2C)   |       | - Sensors: MPU6050,DS18B20 |       | - Sensors: MPU6050,     |
  |   [Code T01 - 0.5 pts]  |       | - Actuator: Fan Relay      |       |   DS18B20 + Pump Relay  |
  | - Built-in Tasmota      |       | - On-device TinyML[T04,T05]|       | - Custom Local Webserver|
  |   Local Web UI          |       | - Custom Webserver [T07]   |       |   [Code T07 - 1.0 pt]   |
  +------------+------------+       +-------------+--------------+       +------------+------------+
               |                                  |                                   |
               | Wi-Fi (MQTT/HTTP)                | BLE [T03 - 1.5 pts]               | BLE [T03]
               |                                  | (Bi-directional: Telemetry & Cmd) | (2-way)
               +----------------------------------+-----------------------------------+
                                                  |
                                                  v
====================================================================================================
                           TIER 2: PC LOCAL IOT GATEWAY (PYTHON)
====================================================================================================
  +------------------------------------------------------------------------------------------------+
  |                              LOCAL IOT GATEWAY SOFTWARE (PC / LAPTOP)                          |
  |                                                                                                |
  |  1. Data Aggregation & Command Dispatch Module [T08 - 1.0 pt]:                                 |
  |     - Receives temp/humidity from Board 1 (Wi-Fi) and Fan/Pump data from Board 2, 3 (PC BLE).  |
  |     - Dispatches Relay ON/OFF commands down to Board 2 and Board 3 on demand.                  |
  |                                                                                                |
  |  2. Gateway AI Module [T09 - 1.0 pt]:                                                          |
  |     - Fuses ambient temperature (Board 1) + surface temp/vibration (Board 2, Board 3).         |
  |     - Runs Machine Learning model for combined anomaly detection -> Sends results to Server.   |
  |                                                                                                |
  |  3. Local Monitoring & Control GUI [T10 - 1.0 pt]:                                             |
  |     - Displays real-time temp/vibration charts, AI status, and ON/OFF buttons on PC screen.    |
  +-----------------------------------------------+------------------------------------------------+
                                                  |
                                                  | Internet (MQTT / HTTP)
                                                  | (Uplink Telemetry & Downlink RPC)
                                                  v
====================================================================================================
                               TIER 3: COREIOT CLOUD PLATFORM
====================================================================================================
  +------------------------------------------------------------------------------------------------+
  |                                        COREIOT SERVER                                          |
  |                                                                                                |
  |  +----------------------------+     +---------------------------+     +-----------------------+  |
  |  | Template & Dashboard [T11] |     | Smart RuleChain [T12]     |     | Notification [T13]    |  |
  |  | - Temp & vibration charts  |---->| - Checks temp thresholds  |---->| - Sends alerts to     |  |
  |  | - Remote RPC buttons to    |     |   & AI fault labels       |     |   users via Web,      |  |
  |  |   toggle Fan & Pump        |     | - Auto-sends emergency    |     |   Email, or Telegram  |  |
  |  +----------------------------+     |   RPC shutdown commands   |     +-----------------------+  |
  |                                     +---------------------------+                              |
  +------------------------------------------------------------------------------------------------+
```

## 4. Technology Mapping (Target: 8.0 / 8.0 Max Points)

| Code | Technology Element | Points | System Implementation |
| :--- | :--- | :---: | :--- |
| **T01** | I2C sensor on Tasmota | 0.5 | Board 1 reads `DHT20` via I2C on Tasmota firmware |
| **T03** | BLE communication | 1.5 | Board 2 & Board 3 exchange telemetry and commands with PC via BLE |
| **T04** | On-device TinyML inference | 1.0 | Board 2 runs TinyML model to classify fan vibration states |
| **T05** | TinyML data & training pipeline | 1.0 | Collects `MPU6050` data, trains and exports C++ model via Edge Impulse |
| **T07** | On-device Webserver | 1.0 | Board 2 & Board 3 host custom local web servers for status and relay control |
| **T08** | PC Local IoT Gateway | 1.0 | Python gateway aggregates Wi-Fi/BLE data and dispatches CoreIOT RPC commands |
| **T09** | AI on Local IoT Gateway | 1.0 | Multi-sensor ML anomaly detection combining Board 1, 2, and 3 telemetry |
| **T10** | Local Gateway GUI | 1.0 | Local dashboard on PC for real-time visualization and manual control |
| **T11** | CoreIOT Template & Dashboard | 1.0 | Cloud dashboard for remote monitoring and RPC control |
| **T12** | CoreIOT Smart RuleChain | 1.0 | Automated threshold checking and emergency relay shutdown |
| **T13** | Threshold Alert Notification | 0.5 | Automated alerts via Web, Email, or Telegram when anomalies occur |
| **Total** | **Registered Points** | **10.5** | **Capped at 8.0 / 8.0 pts** |

## 5. Repository Structure

```text
CO3037-Industrial-IoT-Monitoring/
├── firmware/
│   ├── bo1_tasmota_config/      # Board 1: Tasmota template & configuration
│   ├── bo2_fan_node/            # Board 2: PlatformIO C++ project (Fan + TinyML + BLE + Web)
│   └── bo3_pump_node/           # Board 3: PlatformIO C++ project (Pump + BLE + Web)
├── gateway_pc/                  # Python Local Gateway, ML model & Local GUI
├── coreiot/                     # CoreIOT Dashboard & RuleChain exported JSONs
├── tinyml_models/               # Vibration dataset & Edge Impulse model exports
├── docs/                        # Hardware wiring diagrams, test logs & final report
├── .gitignore
└── README.md
```

## 6. Quick Start

### 1. Tier 1 – Field Devices
* **Board 1 (Tasmota):** Flash Tasmota ESP32-S3, wire `DHT20` to `SDA/SCL`, and configure MQTT/HTTP toward the PC Gateway.
* **Board 2 & Board 3 (PlatformIO):**
  ```bash
  cd firmware/bo2_fan_node   # or bo3_pump_node
  pio run --target upload
  pio device monitor
  ```

### 2. Tier 2 – PC Local IoT Gateway
```bash
cd gateway_pc
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 3. Tier 3 – CoreIOT Cloud
1. Import rule chains and dashboard templates from `coreiot/`.
2. Add the Gateway access token into `gateway_pc/.env`.