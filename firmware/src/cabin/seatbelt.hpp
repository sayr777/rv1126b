#pragma once
#include "../rknn/rknn_model.hpp"
#include <functional>
#include <string>

struct SeatbeltResult {
    bool  belt_on;
    float conf;          // confidence of the predicted class
    int   track_id;      // vehicle/driver track this result belongs to
};

// Binary classifier: seatbelt present / absent.
// Input: driver-area crop (cabin camera), resized to 224×224.
// Model: MobileNetV2 INT8 → 2-class softmax.
//
// Expected accuracy: ~93% on balanced dataset at 2 m distance.
// Degrades significantly at angles > 45° or in low light without IR illuminator.
class SeatbeltDetector {
public:
    struct Config {
        std::string model_path;
        float       conf_threshold = 0.75f;  // below this → "uncertain", not reported
        // ROI in normalised coords where the driver torso is expected
        float roi_x1 = 0.0f, roi_y1 = 0.1f, roi_x2 = 0.5f, roi_y2 = 0.9f;
    };

    using Callback = std::function<void(const SeatbeltResult&)>;

    SeatbeltDetector(Config cfg, Callback on_result);

    // frame_bgr: full cabin camera frame; track_id: driver's vehicle ID.
    void process(const uint8_t* frame_bgr, int width, int height, int track_id = -1);

private:
    RknnModel model_;
    Config    cfg_;
    Callback  cb_;

    std::vector<uint8_t> extract_roi(const uint8_t* frame, int w, int h) const;
};
