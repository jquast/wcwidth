cmake_minimum_required(VERSION 3.16)
project(libwcwidth VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

# library
# Keep this source list in parity with pyproject.toml's
# [[tool.setuptools.ext-modules]] sources; the Makefile globs src/*.c itself.

set(LIBWCWIDTH_SOURCES
    src/bisearch.c
    src/wcwidth.c
    src/wcswidth.c
    src/wcstwidth.c
    src/width.c
    src/textwrap.c
    src/clip.c
    src/align.c
    src/grapheme.c
    src/escape.c
    src/sgr.c
    src/text_sizing.c
    src/terminal_override.c
    src/utf8.c
    # Generated tables
    src/tables/table_wide.c
    src/tables/table_zero.c
    src/tables/table_ambiguous.c
    src/tables/table_grapheme.c
    src/tables/table_mc.c
    src/tables/table_vs15.c
    src/tables/table_vs16.c
    src/tables/table_terminal_overrides.c
    src/tables/table_term_programs.c
)

add_library(wcwidth ${LIBWCWIDTH_SOURCES})
add_library(wcwidth::wcwidth ALIAS wcwidth)

target_include_directories(wcwidth
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# tests

option(BUILD_TESTING "Build tests" ON)

if(BUILD_TESTING)
    enable_testing()

    set(TEST_SOURCES
        tests/test_wcwidth.c
        tests/test_wcswidth.c
        tests/test_width.c
        tests/test_textwrap.c
        tests/test_clip.c
        tests/test_align.c
        tests/test_grapheme.c
        tests/test_escape.c
        tests/test_sgr.c
        tests/test_text_sizing.c
    )

    foreach(test_src ${TEST_SOURCES})
        get_filename_component(test_name ${test_src} NAME_WE)
        add_executable(${test_name} ${test_src})
        target_link_libraries(${test_name} PRIVATE wcwidth)
        target_include_directories(${test_name} PRIVATE tests)
        add_test(NAME ${test_name} COMMAND ${test_name})
    endforeach()
endif()

# install

include(GNUInstallDirs)

install(TARGETS wcwidth
    EXPORT libwcwidth-targets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

install(DIRECTORY include/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT libwcwidth-targets
    NAMESPACE wcwidth::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/libwcwidth
)

include(CMakePackageConfigHelpers)
configure_package_config_file(
    cmake/libwcwidth-config.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/libwcwidth-config.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/libwcwidth
)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/libwcwidth-config.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/libwcwidth
)
