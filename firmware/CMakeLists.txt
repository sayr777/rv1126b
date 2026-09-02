cmake_minimum_required(VERSION 3.20)
project(rv1126b_traffic_ai CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD 11)

# RKNN Runtime — set RKNN_RT_LIB to the path of librknnrt.so
if(NOT DEFINED RKNN_SDK_ROOT)
    set(RKNN_SDK_ROOT $ENV{RKNN_SDK_ROOT})
endif()

find_library(RKNN_RT_LIB rknnrt HINTS ${RKNN_SDK_ROOT}/runtime/Linux/librknn_api/aarch64)
if(NOT RKNN_RT_LIB)
    message(FATAL_ERROR "librknnrt.so not found. Set RKNN_SDK_ROOT or install RKNN2 runtime.")
endif()

include_directories(
    src
    ${RKNN_SDK_ROOT}/runtime/Linux/librknn_api/include
)

# Thread support
find_package(Threads REQUIRED)

set(SOURCES
    src/main.cpp
    src/pipeline.cpp
    src/camera/v4l2_capture.cpp
    src/camera/dual_cam.cpp
    src/lpr/vehicle_detector.cpp
    src/lpr/plate_detector.cpp
    src/lpr/plate_ocr.cpp
    src/lpr/lpr_pipeline.cpp
    src/waffle/zone.cpp
    src/waffle/bytetrack.cpp
    src/waffle/violation_detector.cpp
    src/cabin/seatbelt.cpp
    src/cabin/phone_detector.cpp
    src/rknn/rknn_model.cpp
    src/rknn/rknn_pool.cpp
    src/output/event_publisher.cpp
    src/output/rtsp_server.cpp
)

add_executable(traffic_ai ${SOURCES})
target_link_libraries(traffic_ai
    ${RKNN_RT_LIB}
    Threads::Threads
)

# Tests
enable_testing()
add_subdirectory(tests)
