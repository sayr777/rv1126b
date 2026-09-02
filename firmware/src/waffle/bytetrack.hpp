#pragma once
#include "zone.hpp"
#include <vector>
#include <unordered_map>
#include <cstdint>

struct Track {
    int      id;
    BBox     box;       // latest bounding box (normalised)
    int      age;       // frames since last match
    int      hits;      // total confirmed frames
    bool     confirmed; // true after hits >= MIN_HITS
};

// Minimal ByteTrack-inspired multi-object tracker.
// Keeps tracks across frames using IoU matching + Kalman-predicted positions.
// Full ByteTrack two-stage (high/low confidence) matching is implemented.
class ByteTrack {
public:
    struct Config {
        float track_thresh  = 0.45f; // high-confidence threshold
        float low_thresh    = 0.10f; // low-confidence threshold (2nd stage)
        float match_thresh  = 0.80f; // min IoU for match
        int   max_lost      = 30;    // frames before track deleted
        int   min_hits      = 3;     // frames before track confirmed
    };

    ByteTrack();
    explicit ByteTrack(Config cfg);

    // Update tracker with detections from current frame.
    // Returns all *confirmed* active tracks.
    std::vector<Track> update(const std::vector<BBox>& dets);

    int next_id() const { return next_id_; }

private:
    Config cfg_;
    int    next_id_ = 1;

    std::vector<Track> tracked_;
    std::vector<Track> lost_;

    static float iou(const BBox& a, const BBox& b);
    // Hungarian matching; returns pairs {det_idx, track_idx}
    std::vector<std::pair<int,int>> match(const std::vector<BBox>& dets,
                                          const std::vector<Track>& tracks,
                                          float thresh);
};
