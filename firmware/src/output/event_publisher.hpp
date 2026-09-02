#pragma once
#include <string>
#include <functional>
#include <chrono>

enum class EventType {
    PLATE_READ,          // номер считан
    WAFFLE_VIOLATION,    // нарушение на вафельной разметке
    NO_SEATBELT,         // нет ремня
    PHONE_IN_HAND,       // телефон в руках
};

struct TrafficEvent {
    EventType   type;
    std::string plate;          // may be empty
    int         track_id;
    std::string zone_name;      // for WAFFLE_VIOLATION
    double      dwell_sec;      // for WAFFLE_VIOLATION
    float       conf;
    std::chrono::system_clock::time_point timestamp;
    std::string jpeg_path;      // path to saved snapshot (empty if not saved)
};

// Publishes events over HTTP POST (JSON) and optionally MQTT.
// Each event is also logged to a local rotating JSON file.
class EventPublisher {
public:
    struct Config {
        std::string http_endpoint;       // e.g. "http://10.0.0.1:8080/event"
        std::string mqtt_broker;         // e.g. "tcp://10.0.0.1:1883"; empty = disabled
        std::string mqtt_topic_prefix;   // e.g. "traffic/cam01"
        std::string log_dir;             // local JSON log directory
        bool        save_snapshots = true;
        std::string snapshot_dir;
    };

    explicit EventPublisher(Config cfg);

    void publish(const TrafficEvent& ev);

private:
    Config cfg_;
    void   post_http(const TrafficEvent& ev, const std::string& json);
    void   post_mqtt(const TrafficEvent& ev, const std::string& json);
    void   write_log(const TrafficEvent& ev, const std::string& json);
    std::string to_json(const TrafficEvent& ev) const;
};
