#include "violation_detector.hpp"

ViolationDetector::ViolationDetector(std::vector<Zone> zones, Config cfg, Callback on_violation)
    : zones_(std::move(zones)), cfg_(cfg), cb_(std::move(on_violation)) {}

void ViolationDetector::attach_plate(int track_id, const std::string& plate) {
    states_[track_id].plate = plate;
}

void ViolationDetector::update(const std::vector<Track>& tracks, float /*fps*/) {
    auto now = std::chrono::steady_clock::now();

    for (auto& track : tracks) {
        if (!track.confirmed) continue;

        // Find which zone (if any) contains the track's centre
        std::string in_zone;
        for (auto& z : zones_) {
            if (z.contains_center(track.box)) { in_zone = z.name(); break; }
        }

        auto& st = states_[track.id];

        if (in_zone.empty()) {
            // Outside every zone — reset dwell state (plate is preserved)
            st.enter_time = {};
            st.zone_name.clear();
            st.fired = false;
            continue;
        }

        if (st.zone_name != in_zone) {
            // New zone entry (or first entry ever for this track)
            st.enter_time = now;
            st.zone_name  = in_zone;
            st.fired      = false;
            // plate stays intact (may have been pre-registered via attach_plate)
        }

        if (st.fired) continue;

        double elapsed = std::chrono::duration<double>(now - st.enter_time).count();
        if (elapsed >= cfg_.dwell_threshold_sec) {
            st.fired = true;
            cb_(ViolationEvent{ track.id, in_zone, st.plate, elapsed, track.box });
        }
    }
}
