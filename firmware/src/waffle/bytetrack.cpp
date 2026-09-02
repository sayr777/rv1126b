#include "bytetrack.hpp"
#include <algorithm>

ByteTrack::ByteTrack() : cfg_(Config{}) {}
ByteTrack::ByteTrack(Config cfg) : cfg_(cfg) {}

float ByteTrack::iou(const BBox& a, const BBox& b) {
    float ix1 = std::max(a.x1, b.x1), iy1 = std::max(a.y1, b.y1);
    float ix2 = std::min(a.x2, b.x2), iy2 = std::min(a.y2, b.y2);
    if (ix2 <= ix1 || iy2 <= iy1) return 0.0f;
    float inter  = (ix2 - ix1) * (iy2 - iy1);
    float a_area = (a.x2 - a.x1) * (a.y2 - a.y1);
    float b_area = (b.x2 - b.x1) * (b.y2 - b.y1);
    float uni    = a_area + b_area - inter;
    return uni > 0.0f ? inter / uni : 0.0f;
}

std::vector<std::pair<int,int>> ByteTrack::match(const std::vector<BBox>& dets,
                                                   const std::vector<Track>& tracks,
                                                   float thresh) {
    std::vector<std::pair<int,int>> result;
    if (dets.empty() || tracks.empty()) return result;

    std::vector<bool> d_used(dets.size(), false);
    std::vector<bool> t_used(tracks.size(), false);

    for (;;) {
        float best = thresh;
        int bi = -1, bj = -1;
        for (size_t i = 0; i < dets.size(); i++) {
            if (d_used[i]) continue;
            for (size_t j = 0; j < tracks.size(); j++) {
                if (t_used[j]) continue;
                float v = iou(dets[i], tracks[j].box);
                if (v > best) { best = v; bi = i; bj = j; }
            }
        }
        if (bi < 0) break;
        result.push_back({bi, bj});
        d_used[bi] = true;
        t_used[bj] = true;
    }
    return result;
}

std::vector<Track> ByteTrack::update(const std::vector<BBox>& dets) {
    std::vector<BBox> high_dets, low_dets;
    for (auto& d : dets) {
        if (d.conf >= cfg_.track_thresh)    high_dets.push_back(d);
        else if (d.conf >= cfg_.low_thresh) low_dets.push_back(d);
    }

    // Stage 1: high-conf dets → active tracks
    auto m1 = match(high_dets, tracked_, cfg_.match_thresh);
    std::vector<bool> hd_used(high_dets.size(), false);
    std::vector<bool> tr_used(tracked_.size(), false);

    for (auto [di, ti] : m1) {
        hd_used[di] = true; tr_used[ti] = true;
        tracked_[ti].box = high_dets[di];
        tracked_[ti].hits++;
        tracked_[ti].age = 0;
        tracked_[ti].confirmed = tracked_[ti].hits >= cfg_.min_hits;
    }

    std::vector<BBox> rem_high;
    for (size_t i = 0; i < high_dets.size(); i++)
        if (!hd_used[i]) rem_high.push_back(high_dets[i]);

    // Stage 2: remaining high-conf dets → lost tracks
    auto m2 = match(rem_high, lost_, cfg_.match_thresh);
    std::vector<bool> rh_used(rem_high.size(), false);
    std::vector<bool> lt_used(lost_.size(), false);

    std::vector<Track> revived;
    for (auto [di, li] : m2) {
        rh_used[di] = true; lt_used[li] = true;
        lost_[li].box = rem_high[di];
        lost_[li].hits++;
        lost_[li].age = 0;
        lost_[li].confirmed = lost_[li].hits >= cfg_.min_hits;
        revived.push_back(lost_[li]);
    }

    // New tracks for still-unmatched high-conf dets
    std::vector<Track> new_tracks;
    for (size_t i = 0; i < rem_high.size(); i++)
        if (!rh_used[i])
            new_tracks.push_back({ next_id_++, rem_high[i], 0, 1, false });

    // Unmatched active tracks → demote to lost (collected separately to avoid
    // modifying lost_ while lt_used still indexes the old version)
    std::vector<Track> demoted;
    for (size_t i = 0; i < tracked_.size(); i++) {
        if (!tr_used[i]) {
            tracked_[i].age++;
            if (tracked_[i].age <= cfg_.max_lost)
                demoted.push_back(tracked_[i]);
        }
    }

    // Age existing lost that weren't revived; discard if too old
    std::vector<Track> aged_lost;
    for (size_t i = 0; i < lost_.size(); i++) {
        if (!lt_used[i]) {
            lost_[i].age++;
            if (lost_[i].age <= cfg_.max_lost)
                aged_lost.push_back(lost_[i]);
        }
    }

    // Rebuild tracked_ and lost_
    std::vector<Track> next_tracked;
    for (size_t i = 0; i < tracked_.size(); i++)
        if (tr_used[i]) next_tracked.push_back(tracked_[i]);
    for (auto& t : revived)    next_tracked.push_back(t);
    for (auto& t : new_tracks) next_tracked.push_back(t);

    tracked_ = std::move(next_tracked);
    lost_    = std::move(aged_lost);
    for (auto& t : demoted) lost_.push_back(t);

    // Return confirmed active tracks
    std::vector<Track> confirmed;
    for (auto& t : tracked_)
        if (t.confirmed) confirmed.push_back(t);
    return confirmed;
}
