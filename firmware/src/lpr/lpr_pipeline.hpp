#pragma once
#include "../rknn/rknn_model.hpp"
#include "../waffle/zone.hpp"  // BBox
#include <functional>
#include <string>
#include <vector>

struct PlateResult {
    int         track_id;
    std::string text;      // recognised plate string, e.g. "А123БВ77"
    float       conf;
    BBox        plate_box; // in original frame coords
};

// Three-stage LPR pipeline running on the RV1126B NPU:
//   1. vehicle_detector  — YOLOv8n @ 640×640  → vehicle bboxes
//   2. plate_detector    — YOLOv8n @ 320×192  → plate bbox in vehicle crop
//   3. plate_ocr         — LPRNet/CRNN @ 94×24 → plate text
//
// Models are loaded once; inference is synchronous (call from a single thread).
class LprPipeline {
public:
    struct Config {
        std::string vehicle_model;   // path to .rknn
        std::string plate_model;
        std::string ocr_model;
        float       vehicle_conf  = 0.45f;
        float       plate_conf    = 0.50f;
        float       ocr_conf      = 0.70f;
        // Classes treated as vehicles in the vehicle model (COCO: 2=car,5=bus,7=truck)
        std::vector<int> vehicle_classes = {2, 5, 7};
    };

    using Callback = std::function<void(const PlateResult&)>;

    LprPipeline(Config cfg, Callback on_plate);

    // Process one frame (BGR, 1080p or as received from V4L2).
    // track_ids maps vehicle bbox index to ByteTrack ID (pass {} to skip ID attachment).
    void process(const uint8_t* frame_bgr, int width, int height,
                 const std::vector<int>& track_ids = {});

private:
    RknnModel vehicle_det_;
    RknnModel plate_det_;
    RknnModel plate_ocr_;
    Config    cfg_;
    Callback  cb_;

    std::vector<BBox> detect_vehicles(const uint8_t* frame, int w, int h);
    BBox              detect_plate(const uint8_t* crop, int w, int h);
    std::string       run_ocr(const uint8_t* plate_crop, int w, int h, float& conf);

    static std::vector<uint8_t> crop_resize(const uint8_t* src, int src_w, int src_h,
                                            const BBox& box, int dst_w, int dst_h);
    static std::vector<BBox> nms(std::vector<BBox> boxes, float iou_thresh);
};
