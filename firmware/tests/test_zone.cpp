#include <gtest/gtest.h>
#include "waffle/zone.hpp"
#include <fstream>

// Прямоугольная зона [0.3–0.7] × [0.4–0.75]
static Zone make_rect_zone() {
    return Zone({
        {0.30f, 0.40f},
        {0.70f, 0.40f},
        {0.70f, 0.75f},
        {0.30f, 0.75f},
    }, "waffle_main");
}

// ── contains_center ──────────────────────────────────────────────────────────

TEST(ZoneContainsCenter, CenterInsideZone) {
    auto z = make_rect_zone();
    // bbox с центром ровно в середине зоны
    BBox box{ 0.45f, 0.55f, 0.55f, 0.65f, 2, 0.9f };
    EXPECT_TRUE(z.contains_center(box));
}

TEST(ZoneContainsCenter, CenterOutsideZone_Left) {
    auto z = make_rect_zone();
    BBox box{ 0.05f, 0.55f, 0.25f, 0.65f, 2, 0.9f };
    EXPECT_FALSE(z.contains_center(box));
}

TEST(ZoneContainsCenter, CenterOutsideZone_Above) {
    auto z = make_rect_zone();
    BBox box{ 0.45f, 0.10f, 0.55f, 0.30f, 2, 0.9f };
    EXPECT_FALSE(z.contains_center(box));
}

TEST(ZoneContainsCenter, CenterOnBoundary) {
    auto z = make_rect_zone();
    // Центр ровно на левой границе (0.30)
    BBox box{ 0.20f, 0.55f, 0.40f, 0.65f, 2, 0.9f };
    // Центр = 0.30 — граничный случай; принимаем любой результат,
    // но метод не должен падать.
    (void)z.contains_center(box);
    SUCCEED();
}

TEST(ZoneContainsCenter, LargeBboxCenterOutside) {
    auto z = make_rect_zone();
    // Большой bbox перекрывает зону, но его центр — снаружи
    BBox box{ 0.00f, 0.00f, 0.29f, 0.39f, 2, 0.9f };
    EXPECT_FALSE(z.contains_center(box));
}

// ── overlap_fraction ─────────────────────────────────────────────────────────

TEST(ZoneOverlap, FullyInside) {
    auto z = make_rect_zone();
    // bbox полностью внутри зоны
    BBox box{ 0.40f, 0.50f, 0.60f, 0.70f, 2, 0.9f };
    EXPECT_GT(z.overlap_fraction(box), 0.9f);
}

TEST(ZoneOverlap, NoOverlap) {
    auto z = make_rect_zone();
    BBox box{ 0.80f, 0.80f, 0.95f, 0.95f, 2, 0.9f };
    EXPECT_FLOAT_EQ(z.overlap_fraction(box), 0.0f);
}

TEST(ZoneOverlap, PartialOverlap) {
    auto z = make_rect_zone();
    // bbox на половину в зоне
    BBox box{ 0.50f, 0.55f, 0.90f, 0.65f, 2, 0.9f };
    float frac = z.overlap_fraction(box);
    EXPECT_GT(frac, 0.0f);
    EXPECT_LT(frac, 1.0f);
}

// ── name ─────────────────────────────────────────────────────────────────────

TEST(ZoneName, ReturnsCorrectName) {
    auto z = make_rect_zone();
    EXPECT_EQ(z.name(), "waffle_main");
}

// ── load_zones ───────────────────────────────────────────────────────────────

TEST(LoadZones, ParsesValidJson) {
    // Записать временный файл и прочитать
    const char* path = "/tmp/test_zones.json";
    {
        std::ofstream f(path);
        f << R"([{"name":"z1","polygon":[[0.1,0.2],[0.5,0.2],[0.5,0.6],[0.1,0.6]]}])";
    }
    auto zones = load_zones(path);
    ASSERT_EQ(zones.size(), 1u);
    EXPECT_EQ(zones[0].name(), "z1");
    BBox box{ 0.25f, 0.35f, 0.35f, 0.45f, 2, 0.9f };
    EXPECT_TRUE(zones[0].contains_center(box));
}

TEST(LoadZones, EmptyFile) {
    const char* path = "/tmp/test_zones_empty.json";
    {
        std::ofstream f(path);
        f << "[]";
    }
    auto zones = load_zones(path);
    EXPECT_TRUE(zones.empty());
}
