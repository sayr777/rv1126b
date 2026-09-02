#pragma once
#include <string>
#include <vector>
#include <functional>
#include <cstdint>

// Captures frames from a V4L2 device (MIPI CSI or USB camera on RV1126B Linux).
// Buffers are memory-mapped; no copy on the hot path.
// Format: V4L2_PIX_FMT_BGR24 requested; driver converts via ISP automatically.
class V4l2Capture {
public:
    struct Config {
        std::string device;           // e.g. "/dev/video0"
        int         width  = 1920;
        int         height = 1080;
        int         fps    = 30;
        int         n_bufs = 4;       // number of mmap buffers
    };

    explicit V4l2Capture(Config cfg);
    ~V4l2Capture();

    V4l2Capture(const V4l2Capture&) = delete;
    V4l2Capture& operator=(const V4l2Capture&) = delete;

    void start();
    void stop();

    // Block until next frame is ready, then call cb(bgr_data, width, height).
    // cb must not block longer than 1/fps seconds.
    using FrameCallback = std::function<void(const uint8_t*, int, int)>;
    void grab_one(FrameCallback cb);

    int width()  const { return cfg_.width;  }
    int height() const { return cfg_.height; }

private:
    Config cfg_;
    int    fd_ = -1;

    struct MmapBuf { void* start; size_t length; };
    std::vector<MmapBuf> bufs_;

    void open_device();
    void init_device();
    void init_mmap();
    void start_capturing();
    void stop_capturing();
    void uninit_device();
    void close_device();
};
