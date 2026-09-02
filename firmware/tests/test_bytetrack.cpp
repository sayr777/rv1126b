#include <gtest/gtest.h>
#include "waffle/bytetrack.hpp"

// ── helpers ───────────────────────────────────────────────────────────────────

static BBox make_box(float cx, float cy, float w = 0.10f, float h = 0.08f,
                     float conf = 0.80f) {
    return BBox{ cx - w/2, cy - h/2, cx + w/2, cy + h/2, 2, conf };
}

// ── Трек создаётся при повторных детекциях ────────────────────────────────────

TEST(ByteTrack, NewTrackAfterMinHits) {
    ByteTrack tracker;

    std::vector<BBox> dets = { make_box(0.5f, 0.5f) };

    // Первые 2 кадра — трек ещё не подтверждён (hits < min_hits=3)
    auto t1 = tracker.update(dets);
    EXPECT_TRUE(t1.empty());

    auto t2 = tracker.update(dets);
    EXPECT_TRUE(t2.empty());

    // 3-й кадр — трек подтверждён
    auto t3 = tracker.update(dets);
    ASSERT_EQ(t3.size(), 1u);
    EXPECT_TRUE(t3[0].confirmed);
}

// ── Одна детекция → один трек ─────────────────────────────────────────────────

TEST(ByteTrack, SingleDetectionSingleTrack) {
    ByteTrack tracker;
    std::vector<BBox> dets = { make_box(0.5f, 0.5f) };

    for (int i = 0; i < 3; i++) tracker.update(dets);
    auto tracks = tracker.update(dets);

    ASSERT_EQ(tracks.size(), 1u);
    EXPECT_EQ(tracks[0].id, 1);
}

// ── Две независимые детекции → два трека ─────────────────────────────────────

TEST(ByteTrack, TwoDetectionsTwoTracks) {
    ByteTrack tracker;
    std::vector<BBox> dets = {
        make_box(0.2f, 0.5f),
        make_box(0.8f, 0.5f),
    };

    for (int i = 0; i < 4; i++) tracker.update(dets);
    auto tracks = tracker.update(dets);

    ASSERT_EQ(tracks.size(), 2u);
    EXPECT_NE(tracks[0].id, tracks[1].id);
}

// ── Persistent ID при движении объекта ───────────────────────────────────────

TEST(ByteTrack, TrackIdPersistsAcrossFrames) {
    ByteTrack tracker;

    // Подтвердить трек
    for (int i = 0; i < 3; i++)
        tracker.update({ make_box(0.50f, 0.50f) });

    // Объект движется на несколько пикселей каждый кадр
    int first_id = -1;
    for (int frame = 0; frame < 10; frame++) {
        float cx = 0.50f + frame * 0.01f;
        auto tracks = tracker.update({ make_box(cx, 0.50f) });
        if (!tracks.empty()) {
            if (first_id == -1) first_id = tracks[0].id;
            EXPECT_EQ(tracks[0].id, first_id)
                << "ID изменился на кадре " << frame;
        }
    }
    EXPECT_NE(first_id, -1);
}

// ── Трек удаляется после потери детекции ─────────────────────────────────────

TEST(ByteTrack, TrackRemovedAfterMaxLost) {
    ByteTrack::Config cfg;
    cfg.max_lost = 5;
    ByteTrack tracker(cfg);

    // Подтвердить трек
    for (int i = 0; i < 3; i++)
        tracker.update({ make_box(0.5f, 0.5f) });

    // Убрать детекцию — max_lost кадров
    for (int i = 0; i < cfg.max_lost + 2; i++)
        tracker.update({});

    // Снова появился — должен быть с новым ID (старый трек удалён)
    for (int i = 0; i < 3; i++)
        tracker.update({ make_box(0.5f, 0.5f) });
    auto tracks = tracker.update({ make_box(0.5f, 0.5f) });

    ASSERT_EQ(tracks.size(), 1u);
    EXPECT_GT(tracks[0].id, 1);  // ID > 1 означает новый трек
}

// ── Нет детекций → нет треков ────────────────────────────────────────────────

TEST(ByteTrack, EmptyDetectionsEmptyTracks) {
    ByteTrack tracker;
    auto tracks = tracker.update({});
    EXPECT_TRUE(tracks.empty());
}

// ── Низкая уверенность не создаёт confirmed-трек сразу ───────────────────────

TEST(ByteTrack, LowConfNotConfirmedImmediately) {
    ByteTrack::Config cfg;
    cfg.track_thresh = 0.45f;
    cfg.low_thresh   = 0.10f;
    ByteTrack tracker(cfg);

    // conf = 0.20 — попадает во второй этап (low-confidence)
    std::vector<BBox> low = { make_box(0.5f, 0.5f, 0.1f, 0.08f, 0.20f) };
    for (int i = 0; i < 5; i++) tracker.update(low);
    auto tracks = tracker.update(low);

    // Трек с низкой conf не должен стать confirmed без high-conf совпадения
    for (auto& t : tracks)
        EXPECT_FALSE(t.confirmed);
}
