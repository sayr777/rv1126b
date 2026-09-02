#include "zone.hpp"
#include <fstream>
#include <algorithm>
#include <nlohmann/json.hpp>

Zone::Zone(std::vector<Point2f> polygon, std::string name)
    : poly_(std::move(polygon)), name_(std::move(name)) {}

bool Zone::point_in_polygon(float px, float py) const {
    bool inside = false;
    int n = static_cast<int>(poly_.size());
    for (int i = 0, j = n - 1; i < n; j = i++) {
        float xi = poly_[i].x, yi = poly_[i].y;
        float xj = poly_[j].x, yj = poly_[j].y;
        bool cross = ((yi > py) != (yj > py)) &&
                     (px < (xj - xi) * (py - yi) / (yj - yi) + xi);
        if (cross) inside = !inside;
    }
    return inside;
}

bool Zone::contains_center(const BBox& box) const {
    float cx = (box.x1 + box.x2) * 0.5f;
    float cy = (box.y1 + box.y2) * 0.5f;
    return point_in_polygon(cx, cy);
}

float Zone::overlap_fraction(const BBox& box) const {
    // Axis-aligned bounding rect of polygon
    float px1 = poly_[0].x, px2 = poly_[0].x;
    float py1 = poly_[0].y, py2 = poly_[0].y;
    for (auto& p : poly_) {
        px1 = std::min(px1, p.x); px2 = std::max(px2, p.x);
        py1 = std::min(py1, p.y); py2 = std::max(py2, p.y);
    }
    float ix1 = std::max(box.x1, px1), iy1 = std::max(box.y1, py1);
    float ix2 = std::min(box.x2, px2), iy2 = std::min(box.y2, py2);
    if (ix2 <= ix1 || iy2 <= iy1) return 0.0f;
    float inter    = (ix2 - ix1) * (iy2 - iy1);
    float box_area = (box.x2 - box.x1) * (box.y2 - box.y1);
    return box_area > 0.0f ? inter / box_area : 0.0f;
}

std::vector<Zone> load_zones(const std::string& json_path) {
    std::ifstream f(json_path);
    nlohmann::json j;
    f >> j;
    std::vector<Zone> zones;
    for (auto& entry : j) {
        std::string name = entry.value("name", "zone");
        std::vector<Point2f> poly;
        for (auto& pt : entry["polygon"])
            poly.push_back({pt[0].get<float>(), pt[1].get<float>()});
        zones.emplace_back(std::move(poly), name);
    }
    return zones;
}
