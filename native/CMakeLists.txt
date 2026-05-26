cmake_minimum_required(VERSION 3.16)
project(splatlib_native VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(splatlib SHARED
    src/splatlib.cpp
    src/propagation/itwom3.0.cpp   # contains both ITM (point_to_point_ITM) and ITWOM (point_to_point)
)

target_include_directories(splatlib
    PUBLIC  include
    PRIVATE src
    PRIVATE src/propagation
)

# Use double precision for the elevation array (elev_t = double)
target_compile_definitions(splatlib PRIVATE
    SPLATLIB_EXPORTS
    ITM_ELEV_DOUBLE
)

if(MSVC)
    target_compile_definitions(splatlib PRIVATE _USE_MATH_DEFINES)
    target_compile_options(splatlib PRIVATE /W3 /wd4244 /wd4305 /wd4101)
else()
    target_compile_options(splatlib PRIVATE -Wall -Wextra -Wno-unused-variable
                                           -Wno-unused-parameter -fvisibility=hidden)
endif()

set_target_properties(splatlib PROPERTIES
    VERSION   ${PROJECT_VERSION}
    SOVERSION 0
    PUBLIC_HEADER include/splatlib.h
)

install(TARGETS splatlib
    LIBRARY       DESTINATION lib
    RUNTIME       DESTINATION bin
    PUBLIC_HEADER DESTINATION include
)
