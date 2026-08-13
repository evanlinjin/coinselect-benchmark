# Builds the Bitcoin Core side of the benchmark against a pinned, already-configured Core tree.
#
# Core's own build system is used to produce the libraries this links against (see `bench.py
# setup`), which is why this needs both the source tree and its build directory:
#
#   cmake -S core-runner -B build/core-runner \
#         -DCORE_SOURCE_DIR=... -DCORE_BUILD_DIR=... -DCMAKE_BUILD_TYPE=Release
#
# `wallet/coinselection.cpp` and `policy/feerate.cpp` are compiled here rather than linked from
# libbitcoin_wallet so the runner does not drag in the wallet's storage backends; both are used
# unmodified from the pinned revision.

cmake_minimum_required(VERSION 3.22)
project(coinselect-bench-core-runner CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Core refuses to build with assertions compiled out (util/check.h #errors on NDEBUG), and its
# own release builds keep them, so strip NDEBUG the same way Core's build does.
foreach(config RELEASE RELWITHDEBINFO MINSIZEREL)
  string(REPLACE "-DNDEBUG" "" CMAKE_CXX_FLAGS_${config} "${CMAKE_CXX_FLAGS_${config}}")
endforeach()

if(NOT DEFINED CORE_SOURCE_DIR OR NOT DEFINED CORE_BUILD_DIR)
  message(FATAL_ERROR "set -DCORE_SOURCE_DIR and -DCORE_BUILD_DIR to the pinned Bitcoin Core tree")
endif()

if(NOT EXISTS "${CORE_BUILD_DIR}/src/bitcoin-build-config.h")
  message(FATAL_ERROR "CORE_BUILD_DIR is not configured: ${CORE_BUILD_DIR}/src/bitcoin-build-config.h is missing")
endif()

add_executable(core-runner
  main.cpp
  "${CORE_SOURCE_DIR}/src/wallet/coinselection.cpp"
  "${CORE_SOURCE_DIR}/src/policy/feerate.cpp"
)

target_include_directories(core-runner PRIVATE
  "${CORE_SOURCE_DIR}/src"
  "${CORE_BUILD_DIR}/src"
  "${CORE_SOURCE_DIR}/src/univalue/include"
)

# Core's static libraries reference each other in both directions, so let the linker resolve
# them as a group rather than guessing an order.
target_link_libraries(core-runner PRIVATE
  -L"${CORE_BUILD_DIR}/lib"
  -L"${CORE_BUILD_DIR}/src/univalue"
  -Wl,--start-group
  bitcoin_util
  bitcoin_crypto
  bitcoin_consensus
  bitcoin_clientversion
  univalue
  -Wl,--end-group
)
