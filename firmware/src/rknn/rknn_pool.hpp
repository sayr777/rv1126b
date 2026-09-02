#pragma once
#include "rknn_model.hpp"
#include <functional>
#include <future>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <vector>

// Pool of N identical RknnModel instances for parallel inference.
// Each instance owns one RKNN context; the NPU serialises access internally
// but returns results faster than a single-context approach when N > 1.
class RknnPool {
public:
    // model_path: .rknn file; pool_size: number of contexts (1–3 recommended)
    RknnPool(const std::string& model_path, int pool_size);
    ~RknnPool();

    using Task = std::function<void(RknnModel&)>;

    // Enqueue an inference task.  Blocks only when all slots are busy.
    std::future<void> submit(Task task);

private:
    struct Worker {
        RknnModel       model;
        std::thread     thread;
        std::queue<std::packaged_task<void()>> queue;
        std::mutex      mtx;
        std::condition_variable cv;
        bool            stop = false;
        Worker(const std::string& path) : model(path) {}
    };

    std::vector<std::unique_ptr<Worker>> workers_;
    size_t next_ = 0;
    std::mutex sched_mtx_;

    void worker_loop(Worker& w);
};
