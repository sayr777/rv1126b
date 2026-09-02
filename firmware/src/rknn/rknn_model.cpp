#include "rknn_model.hpp"
#include <fstream>
#include <stdexcept>
#include <cstring>

static std::vector<uint8_t> read_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f) throw std::runtime_error("Cannot open model: " + path);
    size_t sz = f.tellg();
    f.seekg(0);
    std::vector<uint8_t> buf(sz);
    f.read(reinterpret_cast<char*>(buf.data()), sz);
    return buf;
}

RknnModel::RknnModel(const std::string& model_path) {
    load(model_path);
    query_attrs();
}

RknnModel::~RknnModel() {
    if (ctx_) rknn_destroy(ctx_);
}

RknnModel::RknnModel(RknnModel&& o) noexcept
    : ctx_(o.ctx_), n_inputs_(o.n_inputs_), n_outputs_(o.n_outputs_),
      in_attrs_(std::move(o.in_attrs_)), out_attrs_(std::move(o.out_attrs_))
{
    o.ctx_ = 0;
}

void RknnModel::load(const std::string& path) {
    auto buf = read_file(path);
    int ret = rknn_init(&ctx_, buf.data(), buf.size(), 0, nullptr);
    if (ret < 0)
        throw std::runtime_error("rknn_init failed: " + std::to_string(ret));
}

void RknnModel::query_attrs() {
    rknn_input_output_num io{};
    rknn_query(ctx_, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io));
    n_inputs_  = io.n_input;
    n_outputs_ = io.n_output;

    in_attrs_.resize(n_inputs_);
    for (int i = 0; i < n_inputs_; i++) {
        in_attrs_[i].index = i;
        rknn_query(ctx_, RKNN_QUERY_INPUT_ATTR,
                   &in_attrs_[i], sizeof(rknn_tensor_attr));
    }
    out_attrs_.resize(n_outputs_);
    for (int i = 0; i < n_outputs_; i++) {
        out_attrs_[i].index = i;
        rknn_query(ctx_, RKNN_QUERY_OUTPUT_ATTR,
                   &out_attrs_[i], sizeof(rknn_tensor_attr));
    }
}

bool RknnModel::run(const std::vector<RknnTensor>& inputs,
                    std::vector<RknnTensor>&        outputs) {
    // Set inputs
    std::vector<rknn_input> rk_in(inputs.size());
    for (size_t i = 0; i < inputs.size(); i++) {
        rk_in[i].index        = i;
        rk_in[i].type         = RKNN_TENSOR_UINT8;
        rk_in[i].size         = inputs[i].size;
        rk_in[i].buf          = inputs[i].data;
        rk_in[i].pass_through = 0;
    }
    if (rknn_inputs_set(ctx_, rk_in.size(), rk_in.data()) < 0) return false;
    if (rknn_run(ctx_, nullptr) < 0) return false;

    // Get outputs
    outputs.resize(n_outputs_);
    std::vector<rknn_output> rk_out(n_outputs_);
    for (int i = 0; i < n_outputs_; i++) {
        rk_out[i].index    = i;
        rk_out[i].want_float = 1;  // dequantize automatically
    }
    if (rknn_outputs_get(ctx_, n_outputs_, rk_out.data(), nullptr) < 0)
        return false;

    for (int i = 0; i < n_outputs_; i++) {
        outputs[i].data = rk_out[i].buf;
        outputs[i].size = rk_out[i].size;
        outputs[i].attr = out_attrs_[i];
    }
    rknn_outputs_release(ctx_, n_outputs_, rk_out.data());
    return true;
}
