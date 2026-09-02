#pragma once
#include "bytetrack.hpp"
#include "zone.hpp"
#include <functional>
#include <unordered_map>
#include <chrono>
#include <string>

struct ViolationEvent {
    int         track_id;
    std::string zone_name;
    std::string plate;       // empty until LPR fires
    double      dwell_sec;
    BBox        box;         // position at event time
};

// Detects waffle-zone dwell violations.
// A violation fires when a confirmed track stays in a Zone for >= dwell_threshold seconds.
// Once fired for a given track+zone pair, it does not re-fire until the track leaves and re-enters.
class ViolationDetector {
public:
    using Callback = std::function<void(const ViolationEvent&)>;

    struct Config {
        double dwell_threshold_sec = 3.0;  // seconds before violation fires
    };

    ViolationDetector(std::vector<Zone> zones, Config cfg, Callback on_violation);

    // Called each frame. fps used to convert frame count to seconds.
    void update(const std::vector<Track>& tracks, float fps);

    // Attach a plate to a track_id (called by LPR pipeline when plate is read).
    void attach_plate(int track_id, const std::string& plate);

private:
    struct TrackState {
        std::chrono::steady_clock::time_point enter_time;
        std::string zone_name;
        bool        fired = false;
        std::string plate;
    };

    std::vector<Zone>                   zones_;
    Config                              cfg_;
    Callback                            cb_;
    std::unordered_map<int, TrackState> states_; // track_id → state
};
