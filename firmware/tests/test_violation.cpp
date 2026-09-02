#include <gtest/gtest.h>
#include "waffle/zone.hpp"
#include "waffle/bytetrack.hpp"
#include "waffle/violation_detector.hpp"
#include <chrono>
#include <thread>

static Zone make_zone() {
    return Zone({
        {0.30f, 0.40f}, {0.70f, 0.40f},
        {0.70f, 0.75f}, {0.30f, 0.75f},
    }, "waffle_main");
}

static Track make_track(int id, float cx, float cy) {
    return Track{ id,
                  BBox{ cx-0.05f, cy-0.04f, cx+0.05f, cy+0.04f, 2, 0.9f },
                  0, 5, true };
}

// ── Нарушение при dwell > threshold ──────────────────────────────────────────

TEST(ViolationDetector, FiresAfterDwellThreshold) {
    ViolationDetector::Config cfg;
    cfg.dwell_threshold_sec = 0.1;   // 100 мс для быстрого теста

    int fired = 0;
    ViolationDetector vd({ make_zone() }, cfg,
                         [&](const ViolationEvent&) { fired++; });

    // Трек внутри зоны; симулируем несколько кадров за 150 мс
    auto t = make_track(1, 0.5f, 0.57f);
    vd.update({ t }, 25.0f);
    std::this_thread::sleep_for(std::chrono::milliseconds(150));
    vd.update({ t }, 25.0f);

    EXPECT_EQ(fired, 1);
}

// ── Нет нарушения пока dwell < threshold ─────────────────────────────────────

TEST(ViolationDetector, NoFireBeforeThreshold) {
    ViolationDetector::Config cfg;
    cfg.dwell_threshold_sec = 10.0;  // 10 секунд — не успеем

    int fired = 0;
    ViolationDetector vd({ make_zone() }, cfg,
                         [&](const ViolationEvent&) { fired++; });

    auto t = make_track(1, 0.5f, 0.57f);
    for (int i = 0; i < 5; i++)
        vd.update({ t }, 25.0f);

    EXPECT_EQ(fired, 0);
}

// ── Нарушение не повторяется пока трек не покинет зону ───────────────────────

TEST(ViolationDetector, NoDoubleFire) {
    ViolationDetector::Config cfg;
    cfg.dwell_threshold_sec = 0.05;

    int fired = 0;
    ViolationDetector vd({ make_zone() }, cfg,
                         [&](const ViolationEvent&) { fired++; });

    auto t = make_track(1, 0.5f, 0.57f);
    vd.update({ t }, 25.0f);
    std::this_thread::sleep_for(std::chrono::milliseconds(80));
    // Продолжаем обновлять — нарушение не должно повторяться
    for (int i = 0; i < 10; i++)
        vd.update({ t }, 25.0f);

    EXPECT_EQ(fired, 1);
}

// ── Трек вне зоны — нарушение не фиксируется ─────────────────────────────────

TEST(ViolationDetector, NoFireWhenOutsideZone) {
    ViolationDetector::Config cfg;
    cfg.dwell_threshold_sec = 0.05;

    int fired = 0;
    ViolationDetector vd({ make_zone() }, cfg,
                         [&](const ViolationEvent&) { fired++; });

    auto t = make_track(1, 0.10f, 0.20f);  // снаружи зоны
    vd.update({ t }, 25.0f);
    std::this_thread::sleep_for(std::chrono::milliseconds(80));
    vd.update({ t }, 25.0f);

    EXPECT_EQ(fired, 0);
}

// ── attach_plate передаётся в событие ────────────────────────────────────────

TEST(ViolationDetector, PlateAttachedToEvent) {
    ViolationDetector::Config cfg;
    cfg.dwell_threshold_sec = 0.05;

    std::string received_plate;
    ViolationDetector vd({ make_zone() }, cfg,
                         [&](const ViolationEvent& ev) {
                             received_plate = ev.plate;
                         });

    vd.attach_plate(42, "А123БВ77");

    auto t = make_track(42, 0.5f, 0.57f);
    vd.update({ t }, 25.0f);
    std::this_thread::sleep_for(std::chrono::milliseconds(80));
    vd.update({ t }, 25.0f);

    EXPECT_EQ(received_plate, "А123БВ77");
}

// ── Неподтверждённый трек не запускает нарушение ─────────────────────────────

TEST(ViolationDetector, UnconfirmedTrackIgnored) {
    ViolationDetector::Config cfg;
    cfg.dwell_threshold_sec = 0.05;

    int fired = 0;
    ViolationDetector vd({ make_zone() }, cfg,
                         [&](const ViolationEvent&) { fired++; });

    Track unconfirmed{ 1,
                       BBox{ 0.45f, 0.53f, 0.55f, 0.61f, 2, 0.9f },
                       0, 1, false };  // confirmed = false
    vd.update({ unconfirmed }, 25.0f);
    std::this_thread::sleep_for(std::chrono::milliseconds(80));
    vd.update({ unconfirmed }, 25.0f);

    EXPECT_EQ(fired, 0);
}
