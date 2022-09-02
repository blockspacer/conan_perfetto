cmake_minimum_required(VERSION 3.1.0)
project(perfetto_test_package CXX)

option(COMPILE_WITH_LLVM_TOOLS
  "Enable clang from llvm_tools (conan package)" OFF)

# see https://github.com/Ericsson/codechecker/blob/master/tools/report-converter/README.md#undefined-behaviour-sanitizer
# NOTE: Compile with -g and -fno-omit-frame-pointer
# to get proper debug information in your binary.
# NOTE: Run your program with environment variable UBSAN_OPTIONS=print_stacktrace=1.
# see https://github.com/google/sanitizers/wiki/SanitizerCommonFlags
option(ENABLE_UBSAN
  "Enable Undefined Behaviour Sanitizer" OFF)

# see https://github.com/google/sanitizers/wiki/AddressSanitizerLeakSanitizer
# see https://github.com/Ericsson/codechecker/blob/master/tools/report-converter/README.md#address-sanitizer
# NOTE: Compile with -g and -fno-omit-frame-pointer
# to get proper debug information in your binary.
# NOTE: use ASAN_OPTIONS=detect_leaks=1 LSAN_OPTIONS=suppressions=suppr.txt
# NOTE: You need the ASAN_OPTIONS=symbolize=1
# to turn on resolving addresses in object code
# to source code line numbers and filenames.
# This option is implicit for Clang but it won't do any harm.
# see https://github.com/google/sanitizers/wiki/SanitizerCommonFlags
option(ENABLE_ASAN
  "Enable Address Sanitizer" OFF)

# see https://github.com/Ericsson/codechecker/blob/master/tools/report-converter/README.md#memory-sanitizer
# NOTE: Compile with -g and -fno-omit-frame-pointer
# to get proper debug information in your binary.
option(ENABLE_MSAN
  "Enable Memory Sanitizer" OFF)

# see https://github.com/Ericsson/codechecker/blob/master/tools/report-converter/README.md#thread-sanitizer
# NOTE: Compile with -g
# to get proper debug information in your binary.
option(ENABLE_TSAN
  "Enable Thread Sanitizer" OFF)

set(CMAKE_VERBOSE_MAKEFILE TRUE)

if(COMPILE_WITH_LLVM_TOOLS)
  message(STATUS
    "Using COMPILE_WITH_LLVM_TOOLS")
  # do not check compile in conanbuildinfo
  # cause we will switch to other compiler after conan install
  set(CONAN_DISABLE_CHECK_COMPILER ON)
else(COMPILE_WITH_LLVM_TOOLS)
  message(STATUS
    "Disabled COMPILE_WITH_LLVM_TOOLS")
endif(COMPILE_WITH_LLVM_TOOLS)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(
  # prevent conan_basic_setup from resetting cmake variables
  TARGETS
  KEEP_RPATHS
  # see https://github.com/conan-io/conan/issues/6012
  NO_OUTPUT_DIRS
)

if(ENABLE_MSAN OR ENABLE_TSAN OR ENABLE_ASAN OR ENABLE_UBSAN)
  find_package(cmake_sanitizers REQUIRED)
endif()

find_package(cmake_platform_detection REQUIRED)
run_cmake_platform_detection()

find_package(cmake_helper_utils REQUIRED)

# prefer ASCII for folder names
force_latin_paths() # from cmake_helper_utils (conan package)

# out dirs (CMAKE_*_OUTPUT_DIRECTORY) must be not empty
validate_out_dirs() # from cmake_helper_utils (conan package)

# In-source builds not allowed
validate_out_source_build(WARNING) # from cmake_helper_utils (conan package)

if(ENABLE_MSAN OR ENABLE_TSAN OR ENABLE_ASAN OR ENABLE_UBSAN)
  message(STATUS
    "Using sanitizers")

  if(cmake_build_type_tolower MATCHES "release" )
    message(WARNING
      "Disable sanitizers in Release builds")
  endif()

  # use llvm_tools from conan
  find_program_helper(llvm-symbolizer
    PATHS
      #${CONAN_BIN_DIRS}
      ${CONAN_BIN_DIRS_LLVM_TOOLS}
    NO_SYSTEM_ENVIRONMENT_PATH
    NO_CMAKE_SYSTEM_PATH
    ${ARGUMENTS_UNPARSED_ARGUMENTS}
    REQUIRED
    OUT_VAR LLVM_SYMBOLIZER_PROGRAM
    VERBOSE TRUE
  )

  check_sanitizer_options(
    ENABLE_TSAN ${ENABLE_TSAN}
    ENABLE_ASAN ${ENABLE_ASAN}
    ENABLE_MSAN ${ENABLE_MSAN}
    ENABLE_UBSAN ${ENABLE_UBSAN}
    LLVM_SYMBOLIZER_PROGRAM ${LLVM_SYMBOLIZER_PROGRAM}
  )
else()
  message(STATUS
    "Disabled sanitizers")
endif()

find_package(Threads)

find_package(perfetto REQUIRED)

string(REPLACE "\\" "/" CONAN_PERFETTO_ROOT "${CONAN_PERFETTO_ROOT}")
message(STATUS "CONAN_PERFETTO_ROOT=${CONAN_PERFETTO_ROOT}")

message(STATUS "CONAN_BIN_DIRS_PERFETTO=${CONAN_BIN_DIRS_PERFETTO}")
message(STATUS "perfetto_libperfetto_INCLUDE_DIR=${perfetto_libperfetto_INCLUDE_DIR}")
message(STATUS "perfetto_perfetto-sdk_INCLUDE_DIR=${perfetto_perfetto-sdk_INCLUDE_DIR}")
message(STATUS "perfetto_perfetto-gen_INCLUDE_DIR=${perfetto_perfetto-gen_INCLUDE_DIR}")
message(STATUS "perfetto_perfetto-protos_INCLUDE_DIR=${perfetto_perfetto-protos_INCLUDE_DIR}")

find_program(PERFETTO_protozero_plugin_BIN
    NAMES protozero_plugin
    PATHS
    ${CONAN_BIN_DIRS_PERFETTO}
)
string(REPLACE "\\" "/" PERFETTO_protozero_plugin_BIN "${PERFETTO_protozero_plugin_BIN}")
message(STATUS "PERFETTO_protozero_plugin_BIN=${PERFETTO_protozero_plugin_BIN}")

find_program(PERFETTO_PROTOC_BIN
    NAMES protoc
    PATHS
    ${CONAN_BIN_DIRS_PERFETTO}
)

string(REPLACE "\\" "/" PERFETTO_PROTOC_BIN "${PERFETTO_PROTOC_BIN}")
message(STATUS "PERFETTO_PROTOC_BIN=${PERFETTO_PROTOC_BIN}")

string(REPLACE "\\" "/" CONAN_INCLUDE_DIRS_PERFETTO "${CONAN_INCLUDE_DIRS_PERFETTO}")
message(STATUS "CONAN_INCLUDE_DIRS_PERFETTO=${CONAN_INCLUDE_DIRS_PERFETTO}")

set(PERFETTO_GEN_DIR "${perfetto_perfetto-gen_INCLUDE_DIR}")
string(REPLACE "\\" "/" PERFETTO_GEN_DIR "${PERFETTO_GEN_DIR}")
message(STATUS "PERFETTO_GEN_DIR=${PERFETTO_GEN_DIR}")

set(PERFETTO_PROTOS_DIR "${perfetto_perfetto-protos_INCLUDE_DIR}")
string(REPLACE "\\" "/" PERFETTO_PROTOS_DIR "${PERFETTO_PROTOS_DIR}")
message(STATUS "PERFETTO_PROTOS_DIR=${PERFETTO_PROTOS_DIR}")

set(PERFETTO_BUILDTOOLS_DIR "${perfetto_perfetto-buildtools_INCLUDE_DIR}")
string(REPLACE "\\" "/" PERFETTO_BUILDTOOLS_DIR "${PERFETTO_BUILDTOOLS_DIR}")
message(STATUS "PERFETTO_BUILDTOOLS_DIR=${PERFETTO_BUILDTOOLS_DIR}")

set(protoc_outdir ${CMAKE_CURRENT_BINARY_DIR})

set(protoc_generated_files
  ${protoc_outdir}/chrome_track_event.pbzero.h
  ${protoc_outdir}/chrome_track_event.pbzero.cc
)

set(protoc_input_files
  ${CMAKE_CURRENT_SOURCE_DIR}/proto/chrome_track_event.proto
)

# Set GENERATED properties of your generated source file.
# So cmake won't complain about missing source file.
set_source_files_properties(
  ${protoc_generated_files}
  PROPERTIES GENERATED 1)

set(FULL_PROTOC_CMD
  ${PERFETTO_PROTOC_BIN}
  "-I${CMAKE_CURRENT_SOURCE_DIR}/proto" 
  "-I${PERFETTO_PROTOS_DIR}"
  "--proto_path=${PERFETTO_PROTOS_DIR}"
  "--plugin_out=wrapper_namespace=pbzero:${protoc_outdir}"
  "--plugin=protoc-gen-plugin=${PERFETTO_protozero_plugin_BIN}"
  "${protoc_input_files}"
)

add_custom_command(
  OUTPUT ${protoc_generated_files}
  COMMAND
    "${CMAKE_COMMAND}"
    -E
    echo
    "executing command: ${FULL_PROTOC_CMD}"
  COMMAND
    "${FULL_PROTOC_CMD}"
  # code generator COMMAND will only be launched
  # if some of DEPENDS files were changed.
  DEPENDS
    ${protoc_input_files}
  # NOTE: uses COMMAND_EXPAND_LISTS
  # to support generator expressions
  # see https://cmake.org/cmake/help/v3.13/command/add_custom_target.html
  COMMAND_EXPAND_LISTS
  COMMENT "running ${PERFETTO_PROTOC_BIN}"
  VERBATIM # to support \t for example
)

add_library(perfetto_sdk STATIC ${CONAN_PERFETTO_ROOT}/sdk/perfetto.cc)
target_include_directories(perfetto_sdk PUBLIC 
  # path to perfetto.h
  ${CONAN_INCLUDE_DIRS_PERFETTO}
)
if (TARGET_WINDOWS)
  target_compile_definitions(perfetto_sdk PRIVATE 
    NOMINMAX # WINDOWS: to avoid defining min/max macros
    _WINSOCKAPI_ # WINDOWS: to avoid re-definition in WinSock2.h
    #_USE_MATH_DEFINES
    #_CRT_RAND_S
  )
  target_link_libraries(perfetto_sdk PUBLIC wsock32 ws2_32)
endif()
target_compile_options(perfetto_sdk PRIVATE
  # /W0 is the MSVC-wide option to disable warning messages.
  $<$<CXX_COMPILER_ID:MSVC>:/W0>
  # -w is the GCC-wide option to disable warning messages.
  $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-w>
)

add_executable(${PROJECT_NAME} 
  test_package.cpp
  ${protoc_generated_files}
)
target_link_libraries(${PROJECT_NAME} 
  #CONAN_PKG::perfetto 
  #perfetto::libperfetto 
  perfetto_sdk
  ${CMAKE_THREAD_LIBS_INIT}
)
set_property(TARGET ${PROJECT_NAME} PROPERTY CXX_STANDARD 11)
target_include_directories(${PROJECT_NAME} PRIVATE 
  ${protoc_outdir}
  ${PERFETTO_GEN_DIR}
  # path to perfetto_build_flags.h
  ${PERFETTO_GEN_DIR}/build_config
)
target_compile_definitions(${PROJECT_NAME} PRIVATE 
  NOMINMAX # WINDOWS: to avoid defining min/max macros
  _WINSOCKAPI_ # WINDOWS: to avoid re-definition in WinSock2.h
  #_USE_MATH_DEFINES
  #_CRT_RAND_S
)
target_compile_options(${PROJECT_NAME} PRIVATE
  # /W0 is the MSVC-wide option to disable warning messages.
  $<$<CXX_COMPILER_ID:MSVC>:/W0>
  # -w is the GCC-wide option to disable warning messages.
  $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-w>
)

# from cmake_helper_utils
sanitize_lib(LIB_NAME ${PROJECT_NAME}
  MSAN ${ENABLE_MSAN}
  TSAN ${ENABLE_TSAN}
  ASAN ${ENABLE_ASAN}
  UBSAN ${ENABLE_UBSAN}
)
