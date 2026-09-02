#include <gtest/gtest.h>
#include "output/event_publisher.hpp"
#include <fstream>
#include <filesystem>
#include <nlohmann/json.hpp>

namespace fs = std::filesystem;

// Создаёт publisher с логированием в /tmp и без HTTP/MQTT
static EventPublisher make_publisher(const std::string& log_dir) {
    fs::create_directories(log_dir);
    EventPublisher::Config cfg;
    cfg.http_endpoint  = "";          // отключить HTTP
    cfg.mqtt_broker    = "";          // отключить MQTT
    cfg.log_dir        = log_dir;
    cfg.save_snapshots = false;
    return EventPublisher(cfg);
}

static TrafficEvent make_event(EventType type, const std::string& plate = "") {
    return TrafficEvent{
        type,
        plate,
        42,
        "waffle_main",
        3.5,
        0.91f,
        std::chrono::system_clock::now(),
        "",
    };
}

// ── Публикация записывает файл в log_dir ─────────────────────────────────────

TEST(EventPublisher, WritesLogFile) {
    const std::string dir = "/tmp/ep_test_log";
    fs::remove_all(dir);

    auto pub = make_publisher(dir);
    pub.publish(make_event(EventType::WAFFLE_VIOLATION, "А123БВ77"));

    // Хотя бы один файл .json должен появиться
    bool found = false;
    for (auto& entry : fs::directory_iterator(dir))
        if (entry.path().extension() == ".json") { found = true; break; }

    EXPECT_TRUE(found) << "Лог-файл не создан в " << dir;
}

// ── Лог-файл содержит корректный JSON ────────────────────────────────────────

TEST(EventPublisher, LogFileIsValidJson) {
    const std::string dir = "/tmp/ep_test_json";
    fs::remove_all(dir);

    auto pub = make_publisher(dir);
    pub.publish(make_event(EventType::NO_SEATBELT));

    std::string json_path;
    for (auto& entry : fs::directory_iterator(dir))
        if (entry.path().extension() == ".json")
            json_path = entry.path().string();

    ASSERT_FALSE(json_path.empty());
    std::ifstream f(json_path);
    ASSERT_TRUE(f.is_open());

    nlohmann::json j;
    EXPECT_NO_THROW(f >> j) << "Файл не является валидным JSON";
}

// ── Поле type корректно сериализуется ────────────────────────────────────────

TEST(EventPublisher, EventTypeInJson) {
    const std::string dir = "/tmp/ep_test_type";
    fs::remove_all(dir);

    auto pub = make_publisher(dir);
    pub.publish(make_event(EventType::PHONE_IN_HAND));

    std::string json_path;
    for (auto& entry : fs::directory_iterator(dir))
        if (entry.path().extension() == ".json")
            json_path = entry.path().string();

    std::ifstream f(json_path);
    nlohmann::json j;
    f >> j;

    EXPECT_EQ(j.value("type", ""), "PHONE_IN_HAND");
}

// ── Поле plate корректно сохраняется ─────────────────────────────────────────

TEST(EventPublisher, PlateStoredInJson) {
    const std::string dir = "/tmp/ep_test_plate";
    fs::remove_all(dir);

    auto pub = make_publisher(dir);
    pub.publish(make_event(EventType::WAFFLE_VIOLATION, "Е456КХ177"));

    std::string json_path;
    for (auto& entry : fs::directory_iterator(dir))
        if (entry.path().extension() == ".json")
            json_path = entry.path().string();

    std::ifstream f(json_path);
    nlohmann::json j;
    f >> j;

    EXPECT_EQ(j.value("plate", ""), "Е456КХ177");
}

// ── Несколько событий — несколько записей (или одна с массивом) ───────────────

TEST(EventPublisher, MultipleEventsMultipleLogs) {
    const std::string dir = "/tmp/ep_test_multi";
    fs::remove_all(dir);

    auto pub = make_publisher(dir);
    pub.publish(make_event(EventType::PLATE_READ,       "А111АА77"));
    pub.publish(make_event(EventType::WAFFLE_VIOLATION, "А111АА77"));
    pub.publish(make_event(EventType::NO_SEATBELT));

    int count = 0;
    for (auto& entry : fs::directory_iterator(dir))
        if (entry.path().extension() == ".json") count++;

    EXPECT_GE(count, 1) << "Ожидается хотя бы один лог-файл";
}
