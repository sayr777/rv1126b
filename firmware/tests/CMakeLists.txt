cmake_minimum_required(VERSION 3.20)
project(rv1126b_tests CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

# ── GoogleTest ────────────────────────────────────────────────────────────────
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG        v1.14.0
    GIT_SHALLOW    TRUE
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# ── nlohmann/json (header-only, needed by zone.cpp and test_event_publisher) ─
FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(nlohmann_json)

include(GoogleTest)
enable_testing()

# Общие include-пути
include_directories(../src)

# ── test_zone ─────────────────────────────────────────────────────────────────
add_executable(test_zone
    test_zone.cpp
    ../src/waffle/zone.cpp
)
target_link_libraries(test_zone
    GTest::gtest_main
    nlohmann_json::nlohmann_json
)
gtest_discover_tests(test_zone)

# ── test_bytetrack ────────────────────────────────────────────────────────────
add_executable(test_bytetrack
    test_bytetrack.cpp
    ../src/waffle/bytetrack.cpp
)
target_link_libraries(test_bytetrack GTest::gtest_main)
gtest_discover_tests(test_bytetrack)

# ── test_violation ────────────────────────────────────────────────────────────
add_executable(test_violation
    test_violation.cpp
    ../src/waffle/zone.cpp
    ../src/waffle/bytetrack.cpp
    ../src/waffle/violation_detector.cpp
)
target_link_libraries(test_violation
    GTest::gtest_main
    nlohmann_json::nlohmann_json
)
gtest_discover_tests(test_violation)

# ── test_event_publisher ──────────────────────────────────────────────────────
add_executable(test_event_publisher
    test_event_publisher.cpp
    ../src/output/event_publisher.cpp
)
target_link_libraries(test_event_publisher
    GTest::gtest_main
    nlohmann_json::nlohmann_json
)
gtest_discover_tests(test_event_publisher)

# ── test_lpr (requires RKNN runtime — skipped without it) ────────────────────
if(RKNN_RT_LIB)
    add_executable(test_lpr
        test_lpr.cpp
        ../src/lpr/lpr_pipeline.cpp
        ../src/rknn/rknn_model.cpp
    )
    target_link_libraries(test_lpr GTest::gtest_main ${RKNN_RT_LIB})
    gtest_discover_tests(test_lpr)
endif()
