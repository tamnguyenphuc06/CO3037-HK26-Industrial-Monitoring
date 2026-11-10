# Industrial IoT Monitoring & Predictive Maintenance (CO3037)

Course Project for **Internet of Things (CO3037)** – Semester 261 (2025–2026), Ho Chi Minh City University of Technology (HCMUT).

* **Instructor:** Dr. Le Trong Nhan

## 1. Overview

An end-to-end 3-tier Industrial IoT system monitoring two simulated industrial assets using **ESP32-S3 (Yolo:UNO)** and **CoreIOT**:

* **Node 1 (M1 - Ventilation Fan):** Vibration (`MPU6050`), surface temperature (`DS18B20`), relay control, local webserver, and on-device TinyML anomaly detection.
* **Node 2 (M2 - Water Pump):** Vibration (`MPU6050`), surface temperature (`DS18B20`), relay control, and local webserver.
* **PC Local IoT Gateway:** Bi-directional BLE communication with both nodes, local GUI dashboard, and cloud synchronization with CoreIOT.

## 2. Team Members & Responsibilities

| Member | Full Name | Student ID | GitHub | Role & Core Modules |
| :--- | :--- | :--- | :--- | :--- |
| **TV1** | [Member 1] | [ID 1] | `@user1` | **PC Gateway & Cloud:** `gateway.py`, `ble_client.py`, `simulate_nodes.py`, Local GUI, CoreIOT |
| **TV2** | [Member 2] | [ID 2] | `@user2` | **Sensors & TinyML:** `fan_sensors.cpp/.h`, `collect_samples.py`, Edge Impulse pipeline, `tinyml.cpp/.h` |
| **TV3** | [Member 3] | [ID 3] | `@user3` | **Core Firmware & Hardware:** `config_fan.h`, `config_pump.h`, `ble_service.cpp/.h`, `relay.cpp/.h`, Local Webserver, Wiring |

## 3. System Architecture

```text
====================================================================================================
                          TIER 1: FIELD DEVICES & SENSORS (2x ESP32-S3)
====================================================================================================

        +------------------------------------+          +------------------------------------+
        |         NODE 1: FAN NODE           |          |        NODE 2: PUMP NODE           |
        |       (C++ / Arduino Code)         |          |       (C++ / Arduino Code)         |
        +------------------------------------+          +------------------------------------+
        | - Sensors: MPU6050, DS18B20        |          | - Sensors: MPU6050, DS18B20        |
        | - Actuator: Fan Relay              |          | - Actuator: Pump Relay             |
        | - On-device TinyML [T04, T05]      |          | - Custom Local Webserver           |
        | - Custom Local Webserver [T07]     |          |   [Code T07 - 1.0 pt]              |
        +-----------------+------------------+          +-----------------+------------------+
                          |                                               |
                          | BLE [T03 - 1.5 pts]                           | BLE [T03 - 1.5 pts]
                          | (Bi-directional: Telemetry & Commands)        | (Bi-directional)
                          +-----------------------+-----------------------+
                                                  |
                                                  v
====================================================================================================
                           TIER 2: PC LOCAL IOT GATEWAY (PYTHON)
====================================================================================================
  +------------------------------------------------------------------------------------------------+
  |                              LOCAL IOT GATEWAY SOFTWARE (PC / LAPTOP)                          |
  |                                                                                                |
  |  1. Data Aggregation & Command Dispatch Module [T08 - 1.0 pt]:                                 |
  |     - Connects to Fan Node and Pump Node via BLE (`ble_client.py`) or Mock (`simulate_nodes`). |
  |     - Validates packets, tracks node state, and dispatches Relay ON/OFF commands (`gateway.py`)|
  |                                                                                                |
  |  2. Local Monitoring & Control GUI [T10 - 1.0 pt]:                                             |
  |     - Displays real-time temperature/vibration charts, TinyML status, and ON/OFF controls.     |
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
  |  | - Remote RPC buttons to    |     |   & TinyML fault labels   |     |   users via Web,      |  |
  |  |   toggle Fan & Pump        |     | - Auto-sends emergency    |     |   Email, or Telegram  |  |
  |  +----------------------------+     |   RPC shutdown commands   |     +-----------------------+  |
  |                                     +---------------------------+                              |
  +------------------------------------------------------------------------------------------------+
```

## 4. Technology Mapping (Target: 8.0 / 8.0 Max Points)

| Code | Technology Element | Points | System Implementation |
| :--- | :--- | :--- | :--- |
| **T03** | BLE communication | 1.5 | Fan & Pump nodes exchange telemetry and relay commands with PC via BLE |
| **T04** | On-device TinyML inference | 1.0 | Fan node runs TinyML model to classify vibration states in real time |
| **T05** | TinyML data & training pipeline | 1.0 | Collects `MPU6050` data via Serial (`collect_samples.py`), trains on Edge Impulse |
| **T07** | On-device Webserver | 1.0 | Fan & Pump nodes host custom local web servers for status and relay control |
| **T08** | PC Local IoT Gateway | 1.0 | Python gateway aggregates BLE data and dispatches CoreIOT RPC commands |
| **T10** | Local Gateway GUI | 1.0 | Local dashboard on PC for real-time visualization and manual control |
| **T11** | CoreIOT Template & Dashboard | 1.0 | Cloud dashboard for remote monitoring and RPC control |
| **T12** | CoreIOT Smart RuleChain | 1.0 | Automated threshold checking and emergency relay shutdown |
| **T13** | Threshold Alert Notification | 0.5 | Automated alerts via Web, Email, or Telegram when anomalies occur |
| **Total** | **Registered Points** | **9.0** | **Capped at 8.0 / 8.0 pts** |

## 5. Repository Structure

```text
CO3037-Industrial-IoT-Monitoring/
├── firmware/                    # Shared PlatformIO project for Fan & Pump nodes
│   ├── include/
│   │   ├── config_fan.h         # Pinout, UUIDs, intervals for Fan Node
│   │   ├── config_pump.h        # Pinout, UUIDs, intervals for Pump Node
│   │   ├── fan_sensors.h        # MPU6050 & DS18B20 interface
│   │   ├── ble_service.h        # BLE telemetry & command interface
│   │   ├── relay.h              # Relay control interface
│   │   └── tinyml.h             # Edge Impulse TinyML wrapper (Fan Node)
│   ├── src/
│   │   ├── main.cpp             # Main application loop (supports mock & real modes)
│   │   ├── fan_sensors.cpp
│   │   ├── ble_service.cpp
│   │   ├── relay.cpp
│   │   └── tinyml.cpp
│   └── platformio.ini           # Multi-environment build config (env:fan, env:pump)
├── gateway_pc/                  # Python Local IoT Gateway
│   ├── gateway.py               # Core packet handler, validation & state manager
│   ├── ble_client.py            # Bleak BLE client for Fan & Pump nodes
│   ├── simulate_nodes.py        # Mock data & fault injector for offline testing
│   └── requirements.txt
├── tinyml_pipeline/             # TinyML data collection & Edge Impulse assets
│   ├── collect_samples.py       # Serial-to-CSV vibration logger
│   ├── huong_dan_thu_mau.md     # Sampling protocol & sensor mounting guide
│   └── sample_data/             # Reference CSV datasets
├── coreiot/                     # CoreIOT Dashboard & RuleChain exported JSONs
├── docs/                        # Hardware wiring diagrams & final report
├── .gitignore
└── README.md
```

## 6. Quick Start

### 1. Tier 1 – Firmware (PlatformIO)

```bash
cd firmware
# Build & upload for Fan Node
pio run -e fan_node --target upload

# Build & upload for Pump Node
pio run -e pump_node --target upload
```

### 2. Tier 2 – PC Local IoT Gateway

```bash
cd gateway_pc
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run with simulated nodes (before hardware arrives)
python gateway.py --mode mock

# Run with real BLE nodes
python gateway.py --mode ble
```

### 3. TinyML Data Collection

```bash
cd tinyml_pipeline
python collect_samples.py --port COM3 --label normal --duration 10
```