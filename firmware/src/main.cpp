#include "pipeline.hpp"
#include <csignal>
#include <iostream>
#include <fstream>
#include <nlohmann/json.hpp>  // header-only JSON (add to CMake via FetchContent)

static Pipeline* g_pipeline = nullptr;

static void on_signal(int) {
    if (g_pipeline) g_pipeline->stop();
}

static Pipeline::Config load_config(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("Cannot open config: " + path);
    nlohmann::json j;
    f >> j;

    Pipeline::Config cfg;

    cfg.front_cam.device = j.value("front_cam_dev", "/dev/video0");
    cfg.front_cam.width  = j.value("front_cam_w",  1920);
    cfg.front_cam.height = j.value("front_cam_h",  1080);
    cfg.front_cam.fps    = j.value("front_cam_fps", 25);

    cfg.cabin_cam.device = j.value("cabin_cam_dev", "/dev/video1");
    cfg.cabin_cam.width  = j.value("cabin_cam_w",  1280);
    cfg.cabin_cam.height = j.value("cabin_cam_h",  720);
    cfg.cabin_cam.fps    = j.value("cabin_cam_fps", 25);

    cfg.lpr.vehicle_model = j["models"]["vehicle_det"];
    cfg.lpr.plate_model   = j["models"]["plate_det"];
    cfg.lpr.ocr_model     = j["models"]["plate_ocr"];

    cfg.seatbelt.model_path = j["models"]["seatbelt_cls"];
    cfg.phone.model_path    = j["models"]["phone_det"];

    cfg.violation.dwell_threshold_sec = j.value("dwell_threshold_sec", 3.0);

    cfg.zones = load_zones(j.value("zones_file", "config/zones.json"));

    cfg.publisher.http_endpoint    = j.value("http_endpoint", "");
    cfg.publisher.mqtt_broker      = j.value("mqtt_broker",   "");
    cfg.publisher.mqtt_topic_prefix= j.value("mqtt_topic",    "traffic/cam01");
    cfg.publisher.log_dir          = j.value("log_dir",       "logs");
    cfg.publisher.snapshot_dir     = j.value("snapshot_dir",  "snapshots");

    return cfg;
}

int main(int argc, char* argv[]) {
    const char* config_path = (argc > 1) ? argv[1] : "config/config.json";

    Pipeline::Config cfg;
    try {
        cfg = load_config(config_path);
    } catch (const std::exception& e) {
        std::cerr << "Config error: " << e.what() << "\n";
        return 1;
    }

    Pipeline pipeline(std::move(cfg));
    g_pipeline = &pipeline;

    std::signal(SIGINT,  on_signal);
    std::signal(SIGTERM, on_signal);

    pipeline.run();
    return 0;
}
