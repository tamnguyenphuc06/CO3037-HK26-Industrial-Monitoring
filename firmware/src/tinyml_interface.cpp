#include "tinyml_interface.h"
#include <Arduino.h>

#if defined(USE_FAN_CONFIG)

#include <Fan-Vibration-Predictive-Maintenance_inferencing.h>
#include <math.h>
#include <string.h>

static_assert(EI_CLASSIFIER_RAW_SAMPLE_COUNT == 100,
              "Model expects 100 samples per window");
static_assert(EI_CLASSIFIER_RAW_SAMPLES_PER_FRAME == 3,
              "Model expects ax, ay, az");

static constexpr size_t WINDOW_SAMPLES = EI_CLASSIFIER_RAW_SAMPLE_COUNT;
static constexpr size_t INPUT_SIZE = EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE;
static constexpr size_t STRIDE_SAMPLES = 50; // 1000 ms / 20 ms
static constexpr float CONFIDENCE_MIN = 0.60f;

static float sample_buffer[INPUT_SIZE] = {};
static size_t next_sample = 0; // vi tri ghi tiep (mau cu nhat khi da day)
static uint32_t received_samples = 0;
static int current_state = -1;
static float current_confidence = 0.0f;

// Edge Impulse can doc bo mau theo thu tu thoi gian: ax,ay,az,ax,ay,az...
static int get_signal_data(size_t offset, size_t length, float *out_ptr) {
    if (!out_ptr || offset > INPUT_SIZE || length > INPUT_SIZE - offset) {
        return -1;
    }
    const size_t oldest_offset = next_sample * 3;
    for (size_t i = 0; i < length; ++i) {
        out_ptr[i] = sample_buffer[(oldest_offset + offset + i) % INPUT_SIZE];
    }
    return 0;
}

void tinyml_init() {
    memset(sample_buffer, 0, sizeof(sample_buffer));
    next_sample = 0;
    received_samples = 0;
    current_state = -1;
    current_confidence = 0.0f;
    Serial.printf("[TinyML] Ready: %u samples, %u axes, %u Hz\n",
                  (unsigned)WINDOW_SAMPLES,
                  (unsigned)EI_CLASSIFIER_RAW_SAMPLES_PER_FRAME,
                  (unsigned)EI_CLASSIFIER_FREQUENCY);
}

int tinyml_infer(const SensorData& data) {
    // Doc MPU loi (hoac du lieu khong hop le): reset bo dem, khong tron mau cu.
    const bool mpu_error = (static_cast<uint8_t>(data.status) & SENSOR_ERR_MPU) != 0;
    if (mpu_error || !isfinite(data.ax) || !isfinite(data.ay) || !isfinite(data.az)) {
        received_samples = 0;
        next_sample = 0;
        current_state = -1;
        current_confidence = 0.0f;
        return current_state;
    }

    const size_t base = next_sample * 3;
    sample_buffer[base + 0] = data.ax;
    sample_buffer[base + 1] = data.ay;
    sample_buffer[base + 2] = data.az;
    next_sample = (next_sample + 1) % WINDOW_SAMPLES;
    ++received_samples;

    // Lan dau suy luan sau 100 mau (2 s); tiep theo moi 50 mau (1 s).
    if (received_samples < WINDOW_SAMPLES ||
        (received_samples - WINDOW_SAMPLES) % STRIDE_SAMPLES != 0) {
        return current_state;
    }

    signal_t signal;
    signal.total_length = INPUT_SIZE;
    signal.get_data = get_signal_data;

    ei_impulse_result_t result = {};
    const EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
    if (err != EI_IMPULSE_OK) {
        current_state = -1;
        current_confidence = 0.0f;
        Serial.printf("[TinyML] Classification failed: %d\n", (int)err);
        return current_state;
    }

    size_t best = 0;
    for (size_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; ++i) {
        if (result.classification[i].value > result.classification[best].value) {
            best = i;
        }
    }

    current_confidence = result.classification[best].value;
    // Thu tu nhan trong ZIP: fan_idle, fan_low_speed, fan_normal.
    current_state = current_confidence >= CONFIDENCE_MIN ? (int)best : -1;

    Serial.printf("[TinyML] idle=%.2f low=%.2f normal=%.2f => ai=%d (%.2f)\n",
                  result.classification[0].value,
                  result.classification[1].value,
                  result.classification[2].value,
                  current_state,
                  current_confidence);
    return current_state;
}

int tinyml_get_state() { return current_state; }
float tinyml_get_confidence() { return current_confidence; }

#else

void tinyml_init() {}
int tinyml_infer(const SensorData&) { return -1; }
int tinyml_get_state() { return -1; }
float tinyml_get_confidence() { return 0.0f; }

#endif
