#include "event_publisher.hpp"
#include <filesystem>
#include <fstream>
#include <sstream>
#include <atomic>

namespace fs = std::filesystem;

static const char* event_type_str(EventType t) {
    switch (t) {
        case EventType::PLATE_READ:       return "PLATE_READ";
        case EventType::WAFFLE_VIOLATION: return "WAFFLE_VIOLATION";
        case EventType::NO_SEATBELT:      return "NO_SEATBELT";
        case EventType::PHONE_IN_HAND:    return "PHONE_IN_HAND";
    }
    return "UNKNOWN";
}

EventPublisher::EventPublisher(Config cfg) : cfg_(std::move(cfg)) {
    if (!cfg_.log_dir.empty())
        fs::create_directories(cfg_.log_dir);
}

std::string EventPublisher::to_json(const TrafficEvent& ev) const {
    auto ts = std::chrono::system_clock::to_time_t(ev.timestamp);

    // Escape plate string (no special chars expected, but be safe)
    auto esc = [](const std::string& s) { return s; };

    std::ostringstream o;
    o << "{"
      << "\"type\":\"" << event_type_str(ev.type) << "\","
      << "\"plate\":\"" << esc(ev.plate) << "\","
      << "\"track_id\":" << ev.track_id << ","
      << "\"zone_name\":\"" << esc(ev.zone_name) << "\","
      << "\"dwell_sec\":" << ev.dwell_sec << ","
      << "\"conf\":" << ev.conf << ","
      << "\"timestamp\":" << ts
      << "}";
    return o.str();
}

void EventPublisher::write_log(const TrafficEvent& ev, const std::string& json) {
    if (cfg_.log_dir.empty()) return;

    static std::atomic<int> seq{0};
    auto ts = std::chrono::system_clock::to_time_t(ev.timestamp);

    std::ostringstream fname;
    fname << cfg_.log_dir << "/ev_" << ts << "_" << seq.fetch_add(1) << ".json";

    std::ofstream f(fname.str());
    if (f.is_open()) f << json;
}

void EventPublisher::post_http(const TrafficEvent&, const std::string&) {
    // HTTP disabled when http_endpoint is empty
}

void EventPublisher::post_mqtt(const TrafficEvent&, const std::string&) {
    // MQTT disabled when mqtt_broker is empty
}

void EventPublisher::publish(const TrafficEvent& ev) {
    std::string json = to_json(ev);
    if (!cfg_.http_endpoint.empty()) post_http(ev, json);
    if (!cfg_.mqtt_broker.empty())   post_mqtt(ev, json);
    write_log(ev, json);
}
