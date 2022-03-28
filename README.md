# About

modified conan package for perfetto:

* uses `git clone`
* supports sanitizers, see [https://github.com/google/sanitizers/wiki/MemorySanitizerLibcxxHowTo#instrumented-gtest](https://github.com/google/sanitizers/wiki/MemorySanitizerLibcxxHowTo#instrumented-gtest)
* uses `llvm_tools` conan package in builds with `LLVM_USE_SANITIZER`, see https://github.com/google/sanitizers/wiki/MemorySanitizerLibcxxHowTo#instrumented-gtest
* uses `llvm_tools` conan package in builds with libc++ (will be instrumented if `LLVM_USE_SANITIZER` enabled)
* etc.

See `test_package/CMakeLists.txt` for usage example

NOTE: use `-s llvm_tools:build_type=Release` during `conan install`

## Before build

```bash
sudo apt-get update

pushd /tmp
git clone https://android.googlesource.com/platform/external/perfetto/
pushd perfetto
git checkout v13.0
tools/install-build-deps 
popd
popd

# Tested with clang 6.0 and gcc 7
sudo apt-get -y install clang-6.0 g++-7 gcc-7

# llvm-config binary that coresponds to the same clang you are using to compile
export LLVM_CONFIG=/usr/bin/llvm-config-6.0
$LLVM_CONFIG --cxxflags
```

## Local build

```bash
export VERBOSE=1
export CONAN_REVISIONS_ENABLED=1
export CONAN_VERBOSE_TRACEBACK=1
export CONAN_PRINT_RUN_COMMANDS=1
export CONAN_LOGGING_LEVEL=10

conan remote add conan-center https://api.bintray.com/conan/conan/conan-center False

export PKG_NAME=perfetto/v13.0@conan/stable

(CONAN_REVISIONS_ENABLED=1 \
    conan remove --force $PKG_NAME || true)

conan create . \
  conan/stable \
  -s build_type=Release \
  -o perfetto:is_hermetic_clang=False \
  --profile clang \
  --build missing \
  --build cascade

conan upload $PKG_NAME \
  --all -r=conan-local \
  -c --retry 3 \
  --retry-wait 10 \
  --force

# clean build cache
conan remove "*" --build --force
```

## Build with sanitizers support

See options:

```bash
        "is_asan" : [True, False],
        "is_lsan" : [True, False],
        "is_msan" : [True, False],
        "is_tsan" : [True, False],
        "is_ubsan" : [True, False],
```

## conan Flow

```bash
conan source .
conan install --build missing -o perfetto:is_hermetic_clang=False --profile clang -s build_type=Release .
conan build . --build-folder=.
conan package --build-folder=. .
conan export-pkg . conan/stable --settings build_type=Release --force --profile clang
conan test test_package perfetto/v13.0@conan/stable --settings build_type=Release --profile clang
```
