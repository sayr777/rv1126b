cmake_minimum_required(VERSION 3.20)
add_subdirectory(googletest EXCLUDE_FROM_ALL)

add_executable(test_zone
    test_zone.cpp
    ../src/waffle/zone.cpp
)
target_link_libraries(test_zone gtest_main)

add_executable(test_bytetrack
    test_bytetrack.cpp
    ../src/waffle/bytetrack.cpp
)
target_link_libraries(test_bytetrack gtest_main)

add_executable(test_lpr
    test_lpr.cpp
    ../src/lpr/lpr_pipeline.cpp
    ../src/rknn/rknn_model.cpp
)
target_link_libraries(test_lpr gtest_main ${RKNN_RT_LIB})

include(GoogleTest)
gtest_discover_tests(test_zone)
gtest_discover_tests(test_bytetrack)
gtest_discover_tests(test_lpr)
