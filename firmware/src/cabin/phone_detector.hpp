#pragma once
#include "../rknn/rknn_model.hpp"
#include "../waffle/zone.hpp"  // BBox
#include <functional>
#include <string>
#include <vector>

struct PhoneEvent {
    float conf;
    BBox  phone_box;   // location in cabin frame
    int   track_id;
};

// Detects cell phone held by driver.
// Model: YOLOv8n (COCO) — class 67 = "cell phone".
// ROI is limited to the driver-side of the cabin frame to reduce false positives
// (e.g., phones visible through windows or on passenger seat).
//
// Works best at <= 1.5 m distance with good contrast lighting.
// For reliable enforcement, pair with a high-resolution (2MP+) cabin camera.
class PhoneDetector {
public:
    struct Config {
        std::string model_path;
        float       conf_threshold = 0.50f;
        int         coco_phone_cls = 67;
        // Driver-side ROI (normalised); for right-hand traffic, driver is on the left
        float roi_x1 = 0.0f, roi_y1 = 0.0f, roi_x2 = 0.55f, roi_y2 = 1.0f;
    };

    using Callback = std::function<void(const PhoneEvent&)>;

    PhoneDetector(Config cfg, Callback on_phone);

    void process(const uint8_t* frame_bgr, int width, int height, int track_id = -1);

private:
    RknnModel model_;
    Config    cfg_;
    Callback  cb_;

    std::vector<BBox> run_detection(const uint8_t* roi_buf, int w, int h);
    static std::vector<BBox> nms(std::vector<BBox> boxes, float iou_thresh = 0.45f);
};
