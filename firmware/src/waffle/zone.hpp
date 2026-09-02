#pragma once
#include <vector>
#include <string>
#include <cstdint>

struct Point2f { float x, y; };
struct BBox     { float x1, y1, x2, y2; int cls; float conf; };

// A convex polygon zone (вафельная разметка area).
// Coordinates are in normalised image space [0.0, 1.0].
class Zone {
public:
    explicit Zone(std::vector<Point2f> polygon, std::string name = "waffle");

    // Returns true if the centre of bbox lies inside the polygon.
    bool contains_center(const BBox& box) const;

    // Returns overlap area fraction (IoU of box with polygon bounding rect).
    float overlap_fraction(const BBox& box) const;

    const std::string& name() const { return name_; }

private:
    std::vector<Point2f> poly_;
    std::string          name_;

    bool point_in_polygon(float px, float py) const;
};

// Load zone definitions from a JSON file.
// Format:  [ { "name": "waffle_1", "polygon": [[x,y], ...] }, ... ]
std::vector<Zone> load_zones(const std::string& json_path);
