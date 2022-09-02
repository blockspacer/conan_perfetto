from conans import ConanFile, CMake, tools
import os

from conans import ConanFile, CMake, tools, AutoToolsBuildEnvironment, RunEnvironment, python_requires
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.tools import os_info
import os, re, stat, fnmatch, platform, glob, traceback, shutil
from functools import total_ordering

# if you using python less than 3 use from distutils import strtobool
from distutils.util import strtobool

conan_build_helper = python_requires("conan_build_helper/[~=0.0]@conan/stable")

class TestPackageConan(conan_build_helper.CMakePackage):
    name = "perfetto_test_package"
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake", "cmake_find_package"

    # sets cmake variables required to use clang 10 from conan
    def _is_compile_with_llvm_tools_enabled(self):
      return self._environ_option("COMPILE_WITH_LLVM_TOOLS", default = 'false')

    # installs clang 10 from conan
    def _is_llvm_tools_enabled(self):
      return self._environ_option("ENABLE_LLVM_TOOLS", default = 'false')

    def build_requirements(self):
        self.build_requires("cmake_platform_detection/master@conan/stable")
        self.build_requires("cmake_build_options/master@conan/stable")
        self.build_requires("cmake_helper_utils/master@conan/stable")

        # TODO: separate is_lsan
        if self.options['perfetto'].is_tsan \
            or self.options['perfetto'].is_lsan \
            or self.options['perfetto'].is_msan \
            or self.options['perfetto'].is_asan \
            or self.options['perfetto'].is_ubsan:
          self.build_requires("cmake_sanitizers/master@conan/stable")

        # provides clang-tidy, clang-format, IWYU, scan-build, etc.
        if self._is_llvm_tools_enabled():
          self.build_requires("llvm_tools/master@conan/stable")

    def build(self):
        with tools.vcvars(self.settings, only_diff=False): # https://github.com/conan-io/conan/issues/6577
            env_build = AutoToolsBuildEnvironment(self)
            env_build.fpic = self.options['perfetto'].fpic
            with tools.environment_append(env_build.vars):
              cmake = CMake(self)

              #self.output.info("PERFETTO_SDK_DIR={}".format(self.deps_env_info['perfetto'].PERFETTO_SDK_DIR))
              #cmake.definitions['PERFETTO_SDK_DIR'] = self.deps_env_info['perfetto'].PERFETTO_SDK_DIR

              #self.output.info("PERFETTO_GEN_DIR={}".format(self.deps_env_info['perfetto'].PERFETTO_GEN_DIR))
              #cmake.definitions['PERFETTO_GEN_DIR'] = self.deps_env_info['perfetto'].PERFETTO_GEN_DIR

              #self.output.info("PERFETTO_protozero_plugin_BIN={}".format(self.deps_env_info['perfetto'].PERFETTO_protozero_plugin_BIN))
              #cmake.definitions['PERFETTO_protozero_plugin_BIN'] = self.deps_env_info['perfetto'].PERFETTO_protozero_plugin_BIN
              
              #self.output.info("PERFETTO_PROTOC_BIN={}".format(self.deps_env_info['perfetto'].PERFETTO_PROTOC_BIN))
              #cmake.definitions['PERFETTO_PROTOC_BIN'] = self.deps_env_info['perfetto'].PERFETTO_PROTOC_BIN

              #self.output.info("PERFETTO_PROTOS_DIR={}".format(self.deps_env_info['perfetto'].PERFETTO_PROTOS_DIR))
              #cmake.definitions['PERFETTO_PROTOS_DIR'] = self.deps_env_info['perfetto'].PERFETTO_PROTOS_DIR

              # TODO: separate is_lsan
              cmake.definitions['ENABLE_ASAN'] = self.options['perfetto'].is_lsan

              cmake.definitions['ENABLE_UBSAN'] = self.options['perfetto'].is_ubsan
              cmake.definitions['ENABLE_ASAN'] = self.options['perfetto'].is_asan
              cmake.definitions['ENABLE_MSAN'] = self.options['perfetto'].is_msan
              cmake.definitions['ENABLE_TSAN'] = self.options['perfetto'].is_tsan

              self.add_cmake_option(cmake, "COMPILE_WITH_LLVM_TOOLS", self._is_compile_with_llvm_tools_enabled())

              cmake.configure()
              cmake.build()

    def test(self):
        if not tools.cross_building(self):
            #bin_path = os.path.join("bin", "test_package")
            bin_path = os.path.join(self.build_folder, "perfetto_test_package")
            self.run("%s -s" % bin_path, run_environment=True)
            #bin_path = os.path.join(self.build_folder, "perfetto_test_package_with_sdk")
            #self.run("%s -s" % bin_path, run_environment=True)
            #bin_path = os.path.join(self.build_folder, "perfetto_test_package_with_libperfetto")
            #self.run("%s -s" % bin_path, run_environment=True)
