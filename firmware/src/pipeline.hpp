#pragma once
#include "lpr/lpr_pipeline.hpp"
#include "waffle/bytetrack.hpp"
#include "waffle/violation_detector.hpp"
#include "cabin/seatbelt.hpp"
#include "cabin/phone_detector.hpp"
#include "output/event_publisher.hpp"
#include "camera/v4l2_capture.hpp"
#include <atomic>
#include <thread>

// Двухпоточный оркестратор конвейера.
//
// Поток 1 — main_loop (фронтальная камера):
//   Шаг 1. Детекция ТС        — YOLOv8n     → bbox_list
//   Шаг 2. Распознавание номера — plate_det + LPRNet → plate text
//   Шаг 3. Построение трека   — ByteTrack   → Track{id, box, plate}
//   Шаг 4. Вафельная зона     — Zone check + dwell-time → ViolationEvent
//   Публикует active_track_id и plate для кабинного потока.
//
// Поток 2 — cabin_loop (кабинная камера):
//   Шаг 5а. Ремень безопасности — MobileNetV2 → NO_SEATBELT
//   Шаг 5б. Телефон в руках    — YOLOv8n     → PHONE_IN_HAND
//   События привязываются к active_track_id и plate из потока 1.
//   Если confirmed-трека нет — кабинные события не публикуются.
//
// Оба потока разделяют EventPublisher (mutex внутри).
class Pipeline {
public:
    struct Config {
        V4l2Capture::Config       front_cam;
        V4l2Capture::Config       cabin_cam;
        LprPipeline::Config       lpr;
        ViolationDetector::Config violation;
        std::vector<Zone>         zones;
        SeatbeltDetector::Config  seatbelt;
        PhoneDetector::Config     phone;
        EventPublisher::Config    publisher;
        float fps          = 25.0f;
        int   lpr_interval = 5;    // LPR запускается каждые N кадров
        int   min_hits     = 3;    // трек подтверждается после N совпадений
    };

    explicit Pipeline(Config cfg);
    ~Pipeline();

    void run();   // блокирует; прервать через stop()
    void stop();

    // Текущий active_track_id (из шага 3); читается кабинным потоком.
    // -1 = нет confirmed-трека.
    int active_track_id() const { return active_track_id_.load(); }

private:
    Config           cfg_;
    std::atomic_bool running_{false};
    std::atomic_int  active_track_id_{-1};

    // Таблица track_id → plate (пишет main_loop, читает cabin_loop)
    struct TrackPlate { std::string plate; };
    std::unordered_map<int, TrackPlate> track_plates_;
    mutable std::mutex                  track_plates_mtx_;

    void main_loop();
    void cabin_loop();

    std::thread main_thread_;
    std::thread cabin_thread_;
};
