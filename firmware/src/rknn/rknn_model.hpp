#pragma once
#include <rknn_api.h>
#include <string>
#include <vector>
#include <cstdint>

struct RknnTensor {
    void*  data = nullptr;
    size_t size = 0;
    rknn_tensor_attr attr{};
};

// Thin RAII wrapper around a single RKNN model context.
// Thread-safety: one RknnModel must not be called from multiple threads
// simultaneously. Use RknnPool for concurrent inference.
class RknnModel {
public:
    explicit RknnModel(const std::string& model_path);
    ~RknnModel();

    // Disallow copy; allow move
    RknnModel(const RknnModel&) = delete;
    RknnModel& operator=(const RknnModel&) = delete;
    RknnModel(RknnModel&&) noexcept;

    // Run inference. inputs must match the model's input count/shapes.
    // Returns false on RKNN error.
    bool run(const std::vector<RknnTensor>& inputs,
             std::vector<RknnTensor>&       outputs);

    int  num_inputs()  const { return n_inputs_;  }
    int  num_outputs() const { return n_outputs_; }
    const rknn_tensor_attr& input_attr(int i)  const { return in_attrs_[i];  }
    const rknn_tensor_attr& output_attr(int i) const { return out_attrs_[i]; }

private:
    rknn_context ctx_ = 0;
    int n_inputs_  = 0;
    int n_outputs_ = 0;
    std::vector<rknn_tensor_attr> in_attrs_;
    std::vector<rknn_tensor_attr> out_attrs_;

    void load(const std::string& path);
    void query_attrs();
};
