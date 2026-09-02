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

// Top-level orchestrator.
//
//  Thread 1 (main_loop)   — grabs frames from front camera, runs:
//      ByteTrack → ViolationDetector
//      LprPipeline (every 5th frame or on new track)
//
//  Thread 2 (cabin_loop)  — grabs frames from cabin camera, runs:
//      SeatbeltDetector → PhoneDetector
//
// Both threads share an EventPublisher (mutex-protected internally).
class Pipeline {
public:
    struct Config {
        V4l2Capture::Config   front_cam;
        V4l2Capture::Config   cabin_cam;
        LprPipeline::Config   lpr;
        ViolationDetector::Config violation;
        std::vector<Zone>     zones;
        SeatbeltDetector::Config  seatbelt;
        PhoneDetector::Config     phone;
        EventPublisher::Config    publisher;
        float fps = 25.0f;
    };

    explicit Pipeline(Config cfg);
    ~Pipeline();

    void run();   // blocks; call stop() from signal handler to exit
    void stop();

private:
    Config           cfg_;
    std::atomic_bool running_{false};

    void main_loop();
    void cabin_loop();

    std::thread main_thread_;
    std::thread cabin_thread_;
};
