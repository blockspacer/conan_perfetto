import os, re, sys, stat, json, fnmatch, platform, glob, traceback, shutil
from conans import ConanFile, CMake, tools, errors, AutoToolsBuildEnvironment, RunEnvironment, python_requires
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.version import Version
from conans.tools import os_info
from functools import total_ordering

# if you using python less than 3 use from distutils import strtobool
from distutils.util import strtobool

from six import StringIO  # Python 2 and 3 compatible

conan_build_helper = python_requires("conan_build_helper/[~=0.0]@conan/stable")

def merge_two_dicts(x, y):
    z = x.copy()   # start with x's keys and values
    z.update(y)    # modifies z with y's keys and values & returns None
    return z

class PerfettoConan(conan_build_helper.CMakePackage):
    name = "perfetto"

    description = "Performance instrumentation and tracing for Android, Linux and Chrome"
    topics = ("tracing", "google", "instrumentation", "utility")

    homepage = "https://github.com/google/perfetto"
    repo_url = "https://github.com/google/perfetto.git"
    #version = "master"
    branch = "releases/v28.x"
    commit = "99ead408d98eaa25b7819c7e059734bea42fa148"
    version = "master"
    #branch = "master"
    #commit = "cfc11efaad09f07f28857a9fea242db5891a8c63"
    #commit = "0d7ae83e40dc7e39aa73a5965a430ede1ccb26a9"
    url = "https://github.com/google/perfetto"

    license = "MIT"

    exports_sources = ["CMakeLists.txt", "CHANGELOG", "patches/**"]
    short_paths = True

    settings = "os_build", "os", "arch", "compiler", "build_type"

    perfetto_options = {
        "enable_perfetto_version_gen" : [None, True, False],
        "perfetto_enable_git_rev_version_header" : [None, True, False],
        "perfetto_use_system_zlib" : [None, True, False],
        "perfetto_use_system_protobuf" : [None, True, False],
        "enable_perfetto_fuzzers" : [None, True, False],
        # Platform-agnostic unit-tests.
        "enable_perfetto_unittests" : [None, True, False],
        # Build the perf event profiler (traced_perf).
        # TODO(rsavitski): figure out how to make the android-core dependencies build
        # under gcc (_Atomic and other issues).
        "enable_perfetto_traced_perf" : [None, True, False],
        # Makes the heap profiling daemon target reachable. It works only on Android,
        # but is built on Linux as well for test/compiler coverage.
        # On Android, it requires API level 26 due to libunwindstack.
        "enable_perfetto_heapprofd" : [None, True, False],
        # If enable_perfetto_traced_probes is set, enable_perfetto_platform_services
        # must be set as well. Doesn't make sense to build traced_probes without the
        # rest. traced_probes integration tests depend on traced.
        "enable_perfetto_traced_probes" : [None, True, False],
        # Enables the traceconv tool.
        # enable_perfetto_traceconv =
        #    enable_perfetto_tools && enable_perfetto_trace_processor_sqlite
        "enable_perfetto_traceconv" : [None, True, False],
        "enable_perfetto_ui" : [None, True, False],
        # Only for local development. When true the binaries (perfetto, traced, ...)
        # are monolithic and don't use a common shared library. This is mainly to
        # avoid LD_LIBRARY_PATH dances when testing locally.
        # On Windows we default to monolithic executables, because pairing
        # dllexport/import adds extra complexity for little benefit. Te only reason
        # for monolithic_binaries=false is saving binary size, which matters mainly on
        # Android. See also comments on PERFETTO_EXPORT_ENTRYPOINT in compiler.h.
        "monolithic_binaries" : [None, True, False],
        # Whether DLOG should be enabled on debug builds (""), all builds ("on"), or
        # none ("off"). We disable it by default for embedders to avoid spamming their
        # console.
        "perfetto_force_dlog" : [None, True, False],
        # Whether DCHECKs should be enabled or not. Values: "on" | "off" | "".
        # By default ("") DCHECKs are enabled only:
        # - If DCHECK_ALWAYS_ON is defined (which is mainly a Chromium-ism).
        # - On debug builds (i.e. if NDEBUG is NOT defined) but only in Chromium,
        #   Android and standalone builds.
        # - On all other builds (e.g., SDK) it's off regardless of NDEBUG (unless
        #   DCHECK_ALWAYS_ON is defined).
        # See base/logging.h for the implementation of all this.
        "perfetto_force_dcheck" : [None, True, False],
        # Installs a signal handler for the most common crash signals which unwinds
        # the stack and prints the stack trace on stderr. Requires a dependency on
        # libbacktrace when enabled.
        "enable_perfetto_stderr_crash_dump" : [None, True, False],
        "enable_perfetto_x64_cpu_opt" : [None, True, False],
        "enable_perfetto_zlib" : [None, True, False],
        # Misc host executable under tools/.
        "enable_perfetto_tools" : [None, True, False],
        # Enables build of platform-wide tracing services (traced, traced_probes)
        # and executables (perfetto_cmd, trigger_perfetto).
        # When disabled, only the client library and other auxiliary tools can be
        # built (for Chromium and other GN embedders).
        # Note that traced_probes is further conditioned by the GN variable
        # enable_perfetto_traced_probes, in the declare_args() section below.
        "enable_perfetto_platform_services" : [None, True, False],
        "is_cross_compiling" : [None, True, False],
        # Enables base::Watchdog. Is supported only on Linux-based platforms in
        # standalone GN builds (NOT in bazel/blaze).
        # gn/BUILD.gn further restricts this to OS_LINUX || OS_ANDROID when generating
        # the perfetto_build_flags.h header.
        "enable_perfetto_watchdog" : [None, True, False],        
        # The Trace Processor: offline analytical engine to process traces and compute
        # metrics using a SQL engine.
        "enable_perfetto_trace_processor" : [None, True, False],
        "enable_perfetto_trace_processor_httpd" : [None, True, False],
        "enable_perfetto_trace_processor_json" : [None, True, False],
        "enable_perfetto_trace_processor_linenoise" : [None, True, False],
        "enable_perfetto_trace_processor_percentile" : [None, True, False],
        "enable_perfetto_trace_processor_sqlite" : [None, True, False],
        # Benchmarks tracking the performance of: (i) trace writing, (ii) trace readback and (iii) ftrace raw pipe -> protobuf translation.
        "enable_perfetto_benchmarks" : [None, True, False],
        # perfetto_integrationtests - End-to-end tests, involving the protobuf-based IPC transport and ftrace integration (Linux/Android only).
        # NOTE: perfetto_integrationtests requires that the ftrace debugfs directory is is readable/writable by the current user on Linux:
        # sudo chown  -R $USER /sys/kernel/debug/tracing
        "enable_perfetto_integration_tests" : [None, True, False],
        "skip_buildtools_check" : [None, True, False],
        # Background:
        # there are mainly two C++ libraries around in the world: (i) GNU's
        # libstdc++ and LLVM's libc++ (aka libcxx). By default Linux provides libstdc++
        # (even building with clang on Linux uses that by default) while Mac and
        # Android switched to libcxx.
        # buildtools/libcxx(abi) contains a fixed version of the libcxx, the same one
        # that Chrome uses on most production configurations (% lagging catching up
        # with our DEPS).
        # The variable use_custom_libcxx tells our build system to prefer the
        # aforementioned copy to the system one.
        #
        # Now, there are two reasons for using the checked in copy of libcxx:
        # 1) LLVM sanitizers require that the c++ library is built from sources,
        #    because they need to be instrumented with -fsanitize as well (see
        #    https://github.com/google/sanitizers/wiki/MemorySanitizerLibcxxHowTo).
        #    On top of this, they also require that the c++ library is dynamically
        #    linked to prevent duplicate symbol errors when linking (see Chrome's
        #    build/config/c++/c++.gni)
        # 2) The libstdc++ situation is too wild on Linux. Modern debian distros are
        #    fine but Ubuntu Trusty still ships a libstdc++ that doesn't fully
        #    support C++11. Hence we enable this flag on Linux by default.
        #    We still retain libstdc++ coverage on the CI bots by overriding
        #    use_custom_libcxx=false when we target a modern library (see the
        #    GCC target in infra/ci/config.py).
        "use_custom_libcxx" : [None, True, False],
        "custom_libcxx_is_static" : [None, True, False],
        # The Android blueprint file generator set this to true (as well as
        # is_perfetto_build_generator). This is just about being built in the
        # Android tree (AOSP and internal) and is NOT related with the target OS.
        # In standalone Android builds and Chromium Android builds, this is false.
        "perfetto_build_with_android" : [None, True, False],
        # All the tools/gen_* scripts set this to true. This is mainly used to locate
        # .gni files from //gn rather than //build.
        "is_perfetto_build_generator" : [None, True, False],
        # This is for override via `gn args` (e.g. for tools/gen_xxx). Embedders
        # based on GN (e.g. v8) should NOT set this and instead directly sets
        # perfetto_build_with_embedder=true in their GN files.
        "is_perfetto_embedder" : [None, True, False],
        # First of all determine the host toolchain. The user can override this by:
        # 1. setting ar/cc/cxx vars in args.gn.
        # 2. setting is_system_compiler=true in args.gn and the env vars AR/CC/CXX.
        #    This is used by OSSFuzz and CrOS ebuilds.
        # is_system_compiler=True - Disables the scripts that guess the path of the toolchain.
        "is_system_compiler" : [None, True, False],
        # Chromium sets this to true in its //build_overrides/build.gni.
        "build_with_chromium" : [None, True, False],
        "is_nacl" : [None, True, False],
        # This is for override via `gn args` (e.g. for tools/gen_xxx). Embedders
        # based on GN (e.g. v8) should NOT set this and instead directly sets
        # perfetto_build_with_embedder=true in their GN files.
        "perfetto_build_with_embedder" : [None, True, False],
        # NOTE: The IPC layer based on UNIX sockets can't be built on Win.
        # Allow the embedder to use the IPC layer. In turn this allows to use the
        # system backend in the client library.
        # This includes building things that rely on POSIX sockets, this places
        # limitations on the supported operating systems.
        # For now the IPC layer is conservatively not enabled on Chromium+Windows
        # builds.
        "enable_perfetto_ipc" : [None, True, False],
        # is_clang = true  # Will use the hermetic clang-cl toolchain.
        # or
        # is_clang = false  # Will use MSVC 2019.
        "is_clang" : [None, True, False],
        "is_fuzzer" : [None, True, False],
        "use_libfuzzer" : [None, True, False],
        # is_hermetic_clang: Use bundled toolchain from `buildtools/` rather than system-wide one.
        "is_hermetic_clang" : [None, True, False],
        "is_asan" : [None, True, False],
        "is_lsan" : [None, True, False],
        "is_msan" : [None, True, False],
        "is_tsan" : [None, True, False],
        "is_ubsan" : [None, True, False],
    }

    # perfetto gn options
    default_perfetto_options = {
        # Enables the write_version_header.py tool that generates a .h that contains a
        # macro with the current git revision and latest release version from
        # CHANGELOG. If false base/version.h will return "unknown".
        "enable_perfetto_version_gen": None,
        "perfetto_enable_git_rev_version_header": None,
        "perfetto_use_system_zlib": None,
        "perfetto_use_system_protobuf": None,
        "enable_perfetto_unittests": False,
        "enable_perfetto_traced_perf": False,
        "enable_perfetto_heapprofd": False,
        "enable_perfetto_traced_probes": None,
        "enable_perfetto_traceconv": None,
        "enable_perfetto_ui": None,
        "perfetto_force_dlog": None,
        "perfetto_force_dcheck": None,
        "enable_perfetto_stderr_crash_dump": None,
        "enable_perfetto_x64_cpu_opt": None,
        "monolithic_binaries": None,
        "enable_perfetto_zlib": None,
        "enable_perfetto_tools": None,
        "enable_perfetto_platform_services": None,
        "is_cross_compiling": None,
        "enable_perfetto_fuzzers": False,
        "enable_perfetto_benchmarks": False,
        "enable_perfetto_watchdog": False,
        "enable_perfetto_trace_processor": None,
        "enable_perfetto_trace_processor_httpd": None,
        "enable_perfetto_trace_processor_json": None,
        "enable_perfetto_trace_processor_linenoise": None,
        "enable_perfetto_trace_processor_percentile": None,
        "enable_perfetto_trace_processor_sqlite": None,
        "enable_perfetto_integration_tests": False,
        "skip_buildtools_check": True,
        "use_custom_libcxx": None,
        "custom_libcxx_is_static": None,
        "perfetto_build_with_android": None,
        "is_perfetto_build_generator": None,
        "is_perfetto_embedder": None,
        "is_system_compiler": None,
        "build_with_chromium": None,
        "is_nacl": None,
        "perfetto_build_with_embedder": None,
        "enable_perfetto_ipc" : True,
        "is_clang" : True,
        "is_fuzzer" : False,
        "use_libfuzzer" : False,
        "is_hermetic_clang" : None,
        "is_asan" : False,
        "is_lsan" : False,
        "is_msan" : False,
        "is_tsan" : False,
        "is_ubsan" : False
    }

    options = merge_two_dicts({ 
        # Set fpic to True if you want to append the -fPIC flag.
        "fpic": [True, False],
        "check_gn_options": [True, False],
        # NOTE: You may want to generate custom amalgamated source files (sdk/perfetto)
        # if you use cusom buildflags. By default amalgamated source files in sdk/perfetto define buildflags that may differ from gn args provided by you.
        # I use "gen_amalgamated" to change "#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_IPC()"
        # on windows (Windows does not support "enable_perfetto_ipc").
        # Generate the amalgamated source files (sdk/perfetto).
        "gen_amalgamated": [True, False],
        "build_gen_amalgamated": [True, False],
        # try to build examples\sdk\example_startup_trace.cc
        # to test amalgamated source files (sdk/perfetto).
        "build_sdk_examples": [True, False],
        # TEMPORARY FIX FOR v28.x: ../../src/base/unix_socket.cc(332,42): error: unused parameter 'retain' [-Werror,-Wunused-parameter] void UnixSocketRaw::SetRetainOnExec(bool retain)
        # TEMPORARY FIX FOR v13.0: buildtools/android-unwinding/libunwindstack/DwarfOp.cpp:1439:5: error: array designators are a C99 extension [-Werror,-Wc99-designator]
        "warn_no_error": [True, False],
        # set target_os and target_cpu based on conan data
        "append_target_arg": [True, False]
     }, perfetto_options) # merging allows conan to affect gn options

    default_options = merge_two_dicts({
        "fpic": True,
        "check_gn_options": True,
        # TODO: WINDOWS: Building amalgamated project...LINK : fatal error LNK1181: cannot open input file 'protoc.lib'
        # --build: Also compile the generated files
        "build_gen_amalgamated": False,
        # TODO: https://github.com/google/perfetto/issues/345
        "build_sdk_examples": False,
        "gen_amalgamated": False,
        "warn_no_error": True,
        "append_target_arg": False
     }, default_perfetto_options)

    generators = "cmake", "virtualenv"
    build_policy = "missing"

    _cmake = None

    # > gn args out/conan-build --list --short
    # -----------------
    # _android_toolchain_version = "4.9"
    # _default_target_sysroot = ""
    # _target_triplet = ""
    # android_abi_target = "x86_64-linux-android"
    # android_api_level = 21
    # android_app_abi = "x86_64"
    # android_clangrt_dir = "C:/.conan/175948/1/source_subfolder/buildtools/ndk/toolchains/llvm/prebuilt/UNSUPPORTED_ON_WINDOWS/lib64/clang/9.0.9/lib/linux"
    # android_compile_sysroot = "C:/.conan/175948/1/source_subfolder/buildtools/ndk/sysroot/usr/include"
    # android_compile_sysroot_subdir = "x86_64-linux-android"
    # android_host = "UNSUPPORTED_ON_WINDOWS"
    # android_link_sysroot_subdir = "platforms/android-21/arch-x86_64"
    # android_llvm_arch = "x86_64"
    # android_llvm_dir = "C:/.conan/175948/1/source_subfolder/buildtools/ndk/toolchains/llvm/prebuilt/UNSUPPORTED_ON_WINDOWS"
    # android_ndk_root = "C:/.conan/175948/1/source_subfolder/buildtools/ndk"
    # android_prebuilt_arch = "android-x86_64"
    # android_toolchain_root = "C:/.conan/175948/1/source_subfolder/buildtools/ndk/toolchains/x86_64-4.9/prebuilt/UNSUPPORTED_ON_WINDOWS"
    # ar = "ar"
    # cc = "../../buildtools/win/clang/bin\clang-cl.exe"
    # cc_wrapper = ""
    # current_cpu = ""
    # current_os = ""
    # custom_libcxx_is_static = true
    # cxx = "../../buildtools/win/clang/bin\clang-cl.exe"
    # enable_perfetto_benchmarks = false
    # enable_perfetto_fuzzers = false
    # enable_perfetto_heapprofd = false
    # enable_perfetto_integration_tests = false
    # enable_perfetto_ipc = false
    # enable_perfetto_llvm_demangle = false
    # enable_perfetto_platform_services = false
    # enable_perfetto_stderr_crash_dump = false
    # enable_perfetto_tools = false
    # enable_perfetto_trace_processor = false
    # enable_perfetto_trace_processor_httpd = false
    # enable_perfetto_trace_processor_json = false
    # enable_perfetto_trace_processor_linenoise = false
    # enable_perfetto_trace_processor_percentile = false
    # enable_perfetto_trace_processor_sqlite = false
    # enable_perfetto_traceconv = false
    # enable_perfetto_traced_perf = false
    # enable_perfetto_traced_probes = false
    # enable_perfetto_ui = false
    # enable_perfetto_unittests = false
    # enable_perfetto_version_gen = true
    # enable_perfetto_watchdog = false
    # enable_perfetto_x64_cpu_opt = false
    # enable_perfetto_zlib = false
    # extra_cflags = "/W0 -Wno-c99-designator -Wno-unused-parameter -Wno-error "
    # extra_cxxflags = "/W0 -Wno-c99-designator -Wno-unused-parameter -Wno-error "
    # extra_host_cflags = ""
    # extra_host_cxxflags = ""
    # extra_host_ldflags = ""
    # extra_ldflags = ""
    # extra_target_cflags = ""
    # extra_target_cxxflags = ""
    # extra_target_ldflags = ""
    # gcc_toolchain = ""
    # host_cpu = "x64"
    # host_os = "win"
    # is_asan = false
    # is_clang = true
    # is_cross_compiling = false
    # is_debug = true
    # is_fuzzer = false
    # is_hermetic_clang = true
    # is_lsan = false
    # is_lto = false
    # is_msan = false
    # is_perfetto_build_generator = false
    # is_perfetto_embedder = false
    # is_system_compiler = false
    # is_tsan = false
    # is_ubsan = false
    # link_fuzzer = ""
    # linker = "../../buildtools/win/clang/bin\lld-link.exe"
    # monolithic_binaries = true
    # perfetto_build_with_android = false
    # perfetto_enable_git_rev_version_header = true
    # perfetto_force_dcheck = ""
    # perfetto_force_dlog = ""
    # perfetto_use_system_protobuf = false
    # perfetto_use_system_zlib = false
    # perfetto_verbose_logs_enabled = true
    # sanitizer_lib = ""
    # sanitizer_lib_dir = ""
    # sanitizer_lib_dir_is_static = false
    # skip_buildtools_check = false
    # strip = ""
    # sysroot = ""
    # target_ar = "ar"
    # target_cc = "../../buildtools/win/clang/bin\clang-cl.exe"
    # target_cpu = ""
    # target_cxx = "../../buildtools/win/clang/bin\clang-cl.exe"
    # target_gcc_toolchain = ""
    # target_linker = "../../buildtools/win/clang/bin\lld-link.exe"
    # target_os = ""
    # target_strip = ""
    # target_sysroot = ""
    # target_triplet = ""
    # use_custom_libcxx = false
    # use_libfuzzer = false
    # use_sanitizer_configs_without_instrumentation = false
    # using_sanitizer = false
    def log_gn_options(self, build_dir, cwd):
        buf = StringIO()
        self.run('gn args %s --list --short' % (build_dir), output=buf, cwd=cwd)
        output = buf.getvalue()
        self.output.info("gn_options - %s" %(output))

    def get_gn_option_value(self, option_name, build_dir, cwd):
        buf = StringIO()
        self.run('gn args %s --list=%s --short' % (build_dir, option_name), output=buf, cwd=cwd)
        output = buf.getvalue()
        self.output.info("output - %s" %(output))
        pattern = r'%s = (.*)' % (option_name)
        for str in re.findall(pattern, output):
            self.output.info("str - %s" %(str))
            if str == 'true':
                return True
            elif str == 'false':
                return False

        raise errors.ConanInvalidConfiguration("Could not parse gn configuration options because option {} not found in {} due to match {}".format(option_name, output, match))

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    def _patch_sources(self):
        self.output.info("replacing sdk\perfetto.cc")
        try:
            # https://github.com/google/perfetto/issues/347
            tools.replace_in_file(os.path.join(self._source_subfolder, "sdk", "perfetto.cc"), r"    shm = PosixSharedMemory::Create(shmem_size_hint);"
                                , r"""#if PERFETTO_BUILDFLAG(PERFETTO_OS_WIN)
    shm = SharedMemoryWindows::Create(shmem_size_hint);
#else
    shm = PosixSharedMemory::Create(shmem_size_hint);
#endif""")
        except Exception as err:
            self.output.error("replace_in_file sdk\perfetto.cc failed: {0}".format(err))

        # https://github.com/google/perfetto/issues/343
#        self.output.info("replacing unix_socket_unittest in base/BUILD.gn")
#        try:
            #tools.replace_in_file(os.path.join(self._source_subfolder, "src", "base", "BUILD.gn"), r"""    sources += [ "unix_socket_unittest.cc" ]
#    deps += [ ":unix_socket" ]"""
#                                , r"""    if (enable_perfetto_ipc) {
#      sources += [ "unix_socket_unittest.cc" ]
#      deps += [ ":unix_socket" ]
#    }""")
#        except Exception as err:
#            self.output.error("replace_in_file base/BUILD.gn failed: {0}".format(err))

        # https://github.com/google/perfetto/issues/343
        self.output.info("replacing symbolize_database in symbolizer")
        try:
            tools.replace_in_file(os.path.join(self._source_subfolder, "src", "profiling", "symbolizer", "BUILD.gn"), r"""source_set("symbolize_database") {
  public_deps = [
    ":symbolizer",
    "../../../include/perfetto/ext/base",
  ]
  deps = [
    "../../../gn:default_deps",
    "../../../include/perfetto/protozero",
    "../../../include/perfetto/trace_processor:trace_processor",
    "../../../protos/perfetto/trace:zero",
    "../../../protos/perfetto/trace/profiling:zero",
    "../../trace_processor/util:stack_traces_util",
  ]
  sources = [
    "symbolize_database.cc",
    "symbolize_database.h",
  ]
}"""
                                , r"""if (!is_win) {
  source_set("symbolize_database") {
    public_deps = [
      ":symbolizer",
      "../../../include/perfetto/ext/base",
    ]
    deps = [
      "../../../gn:default_deps",
      "../../../include/perfetto/protozero",
      "../../../include/perfetto/trace_processor:trace_processor",
      "../../../protos/perfetto/trace:zero",
      "../../../protos/perfetto/trace/profiling:zero",
      "../../trace_processor/util:stack_traces_util",
    ]
    sources = [
      "symbolize_database.cc",
      "symbolize_database.h",
    ]
  }
}""")
        except Exception as err:
            self.output.error("replace_in_file symbolizer failed: {0}".format(err))

    def _patch_sources_to_gen_amalgamated(self):
        # The CHANGELOG mtime triggers the perfetto_version.gen.h genrule. This is
        # to avoid emitting a stale version information in the remote case of somebody
        # running gen_amalgamated incrementally after having moved to another commit.
        if not os.path.exists(os.path.join(self._source_subfolder, "CHANGELOG")):
            # NOTE: copies CHANGELOG from exports_sources
            self.copy("CHANGELOG", dst=os.path.join(self._source_subfolder, "CHANGELOG"), src=self.source_folder)

        self.output.info("replacing python3 in gn_utils.py")
        try:
            # FIXES subprocess.check_output exit status "9009"
            # https://bugs.python.org/issue20117
            tools.replace_in_file(os.path.join(self._source_subfolder, "tools", "gn_utils.py"), r"return ['python3', wrapper, name]"
                                , r"return [sys.executable, wrapper, name]")
        except Exception as err:
            self.output.error("replace_in_file gn_utils.py failed: {0}".format(err))

        self.output.info("replacing import in gn_utils.py")
        try:
            # FIXES subprocess.check_output exit status "9009"
            # https://bugs.python.org/issue20117
            tools.replace_in_file(os.path.join(self._source_subfolder, "tools", "gn_utils.py"), r"from compat import iteritems"
                                , r"""from compat import iteritems
from platform import system""")
        except Exception as err:
            self.output.error("replace_in_file gn_utils.py failed: {0}".format(err))

        self.output.info("replacing splitext in gn_utils.py")
        try:
            # FIXES "def compute_source_dependencies" if
            # os.path.splitext(line)=('    ../../buildtools/win/clang/lib/clang/16.0.0/include/vadefs', '.h\r')
            # or if
            # os.path.splitext(line)=('    ../../buildtools/protobuf/src/google/protobuf/port_def', '.inc\r')
            tools.replace_in_file(os.path.join(self._source_subfolder, "tools", "gn_utils.py"), r"assert os.path.splitext(line)[1] in ['.c', '.cc', '.cpp', '.S']"
                                , r"assert os.path.splitext(line)[1] in ['.h', '.h\r', '.h', '.inc\r', '.c', '.cc', '.cpp', '.obj' if system().lower() == 'windows' else '.S']")
        except Exception as err:
            self.output.error("replace_in_file gn_utils.py failed: {0}".format(err))

        # TODO: cxx = 'clang-cl' if windows and is_clang=true
        #
        #if sys.platform.startswith('linux'):
        #  llvm_script = os.path.join(gn_utils.repo_root(), 'gn', 'standalone',
        #                             'toolchain', 'linux_find_llvm.py')
        #  cxx = subprocess.check_output([llvm_script]).splitlines()[2].decode()
        #else:
        #  cxx = 'clang++'

        self.output.info("replacing source_deps in gen_amalgamated")
        try:
            tools.replace_in_file(os.path.join(self._source_subfolder, "tools", "gen_amalgamated"), r"    deps = self.source_deps[source_name]"
                                , r"""
    if source_name not in self.source_deps:
      # TODO: KeyError: 'src/base/android_utils.cc'
      return
    deps = self.source_deps[source_name]
""")
        except Exception as err:
            self.output.error("replace_in_file gen_amalgamated failed: {0}".format(err))

        self.output.info("replacing result[-1] in gen_amalgamated")
        try:
            tools.replace_in_file(os.path.join(self._source_subfolder, "tools", "gen_amalgamated"), r"        result[-1] += flag"
                                , r"""
        # If result is empty, then result[-1] yields "list index out of range" error. 
        # Trying to access result[-1] in an empty array is just as invalid as result[0]
        if len(result) == 0:
          result = [flag]
        else:
          result[-1] += flag
""")
        except Exception as err:
            self.output.error("replace_in_file gen_amalgamated failed: {0}".format(err))

        if self.settings.os == 'Windows':
            self.output.info("replacing touch in gen_amalgamated")
            try:
                # TODO: use some windows command instead of "touch"
                tools.replace_in_file(os.path.join(self._source_subfolder, "tools", "gen_amalgamated"), r"  subprocess.check_call(['touch', '-c', changelog_path])"
                                    , "")
            except Exception as err:
                self.output.error("replace_in_file gen_amalgamated failed: {0}".format(err))

    def _patch_sources_to_warn_no_error(self):
        if self.settings.os == 'Windows':
            # TODO: on WINDOWS enable_perfetto_tools error: assert(enable_perfetto_ipc)
            # because tools/websocket_bridge uses ipc:default_socket
            self.output.info("replacing websocket_bridge in BUILD.gn")
            try:
                tools.replace_in_file(os.path.join(self._source_subfolder, "BUILD.gn"), r"if (enable_perfetto_tools)"
                                    , r"""if (is_win && enable_perfetto_tools) {
  all_targets += [
    "src/tools"
  ]
} else if (enable_perfetto_tools) {
  all_targets += [
    "src/tools",
    "src/websocket_bridge",
  ]
}
if (false)""")
            except Exception as err:
                self.output.error("replace_in_file BUILD.gn failed: {0}".format(err))

        self.output.info("replacing WX in gn\standalone\BUILD.gn")
        try:
            tools.replace_in_file(os.path.join(self._source_subfolder, "gn", "standalone", "BUILD.gn"), "cflags += [ \"/WX\" ]" , "cflags += [ \"/W0\" ]")
        except Exception as err:
            self.output.error("replace_in_file gn/standalone/BUILD.gn failed: {0}".format(err))

        self.output.info("replacing Werror in gn\standalone\BUILD.gn")
        try:
            tools.replace_in_file(os.path.join(self._source_subfolder, "gn", "standalone", "BUILD.gn"), "cflags += [ \"-Werror\" ]" , "cflags += [ \"-Wno-error\" ]")
        except Exception as err:
            self.output.error("replace_in_file gn/standalone/BUILD.gn failed: {0}".format(err))
            
        #self.output.info("replacing extra_warnings in gn\standalone\BUILDCONFIG.gn")
        #try:
        #    tools.replace_in_file(os.path.join(self._source_subfolder, "gn", "standalone", "BUILDCONFIG.gn"), "\"//gn/standalone:extra_warnings\"," , "")
        #except Exception as err:
        #    self.output.error("replace_in_file BUILDCONFIG.gn failed: {0}".format(err))

        if self.settings.os == 'Windows':
            try:
                self.output.info("replacing msvc_base in win_find_msvc.py")
                tools.replace_in_file(os.path.join(self._source_subfolder, "gn", "standalone", "toolchain", "win_find_msvc.py"),
                                r"out[1] = find_max_subdir(lib_base, filt)"
                                ,
                                r"""out[1] = find_max_subdir(lib_base, filt)
  for version in ['BuildTools', 'Community', 'Professional', 'Enterprise']:
    for year in ['2022', '2021', '2020', '2019', '2018', '2017']:
        msvc_base = ('C:\\Program Files (x86)\\Microsoft Visual Studio\\{}\\'
                    '{}\\VC\\Tools\\MSVC').format(year, version)
        if os.path.exists(msvc_base):
            filt = lambda x: os.path.exists(
                os.path.join(x, 'lib', 'x64', 'libcmt.lib'))
            max_msvc = find_max_subdir(msvc_base, filt)
            if max_msvc is not None:
                out[2] = os.path.join(msvc_base, max_msvc)
            break""")
            except Exception as err:
                self.output.error("replace_in_file gn/standalone/toolchain/win_find_msvc.py failed: {0}".format(err))

    def configure(self):
        if self.settings.compiler.cppstd:
            tools.check_min_cppstd(self, 11)

        lower_build_type = str(self.settings.build_type).lower()

        if self.settings.os == 'Windows':
            # TODO: on WINDOWS:
            # enable_perfetto_tools error: assert(enable_perfetto_ipc)
            # because tools/websocket_bridge uses ipc:default_socket
            self.options.enable_perfetto_tools = False
            self.perfetto_options['enable_perfetto_tools'] = False
            # TODO: on WINDOWS:
            # ERROR at //src/tracing/ipc/service/BUILD.gn:18:1: Assertion failed.
            # assert(enable_perfetto_ipc)
            # ^-----
            # See //src/traced/service/BUILD.gn:44:5: which caused the file to be included.
            #     "../../tracing/ipc/service",
            #self.options.enable_perfetto_platform_services = False
            #self.perfetto_options['enable_perfetto_platform_services'] = False
            # TODO: on WINDOWS:
            # ERROR Unresolved dependencies.
            # //src/base/http:http(//gn/standalone/toolchain:msvc)
            # needs //src/base:unix_socket(//gn/standalone/toolchain:msvc)
            self.options.enable_perfetto_trace_processor = False
            self.perfetto_options['enable_perfetto_trace_processor'] = False

        #if self.settings.os == 'Windows':
            #self.output.warn("enable_perfetto_ipc=False because self.settings.compiler is %s and self.settings.os is %s" % (self.settings.compiler, self.settings.os))
            # NOTE: The IPC layer based on UNIX sockets can't be built on Win.
            #self.options.enable_perfetto_ipc = False
            #self.perfetto_options['enable_perfetto_ipc'] = False

        #if self._is_clang_cl:
        #    self.output.warn("use_bundled_compiler=True because self.settings.compiler is %s and self.settings.os is %s" % (self.settings.compiler, self.settings.os))
        #    self.options.use_bundled_compiler = True
        #    self.options.append_target_arg = False

        #if not self.perfetto_options['is_hermetic_clang']:
        #    # is_hermetic_clang: Use bundled toolchain from buildtools/ rather than system-wide one.
        #    if self.settings.compiler == "apple-clang" or self.settings.compiler == "clang" or self.settings.compiler == "clang-cl":
        #        self.perfetto_options['is_clang'] = True
        #    else:
        #        self.perfetto_options['is_clang'] = False

        if self.settings.build_type == "Debug":
            self.perfetto_options['is_debug'] = True
        else:
            self.perfetto_options['is_debug'] = False

        if self.settings.os == 'Windows':
            # The https://cs.android.com/android/platform/superproject/+/master:external/perfetto/gn/standalone/toolchain/win_find_msvc.py script will locate the higest version numbers available 
            # from C:\Program Files (x86)\Windows Kits\10
            # and C:\Program Files (x86)\Microsoft Visual Studio\2019.
            if not os.path.exists(r"C:\Program Files (x86)\Windows Kits\10"):
                raise errors.ConanInvalidConfiguration(r"not found: C:\Program Files (x86)\Windows Kits\10")
            if not os.path.exists(r"C:\Program Files (x86)\Microsoft Visual Studio\2019"):
                raise errors.ConanInvalidConfiguration(r"not found: C:\Program Files (x86)\Microsoft Visual Studio\2019")
                
        # options with 'None' will not be overriden
        # i.e. 'None' allows perfetto to choose default value
        for k,v in self.options.items():
            self.output.info("detected conan option %s=%s" % (k,v))
            if k in self.perfetto_options:
                self.output.info("detected perfetto option %s=%s" % (k,v))
                if v is None or str(v).lower() == "none":
                    self.output.info("deleted from perfetto options %s=%s" % (k,v))
                    del self.perfetto_options[k]

    # mkdir .venv ; cd .venv ; conan install .. -g=virtualenv --profile clang_cl -s build_type=Debug -s cling_conan:build_type=Release -s llvm_tools:build_type=Release --build missing ; ./activate.ps1 ; (Get-ChildItem env:path).Value
    def build_requirements(self):
        self.build_requires("cmake_platform_detection/master@conan/stable")
        self.build_requires("cmake_build_options/master@conan/stable")
        self.build_requires("cmake_helper_utils/master@conan/stable")
        self.tool_requires("google_gn/master@conan/stable")
        self.tool_requires("ninja/[>=1.11]")
        self.tool_requires("protobuf/v3.9.1@conan/stable")

    def source(self):
        python_executable = sys.executable
        self.run('git clone -b {} --progress --depth 100 --recursive --recurse-submodules {} {}'.format(self.branch, self.repo_url, self._source_subfolder))
        if self.commit:
            with tools.chdir(self._source_subfolder):
                self.run('git checkout {}'.format(self.commit))
        with tools.chdir(self._source_subfolder):
            self.run('{python} tools/install-build-deps'.format(python=python_executable))

    @property
    def _is_msvc(self):
        return str(self.settings.compiler) in ["Visual Studio", "msvc"]

    @property
    def _is_clang_cl(self):
        return self.settings.compiler == 'clang' and self.settings.os == 'Windows'

    @property
    def _is_clang_x86(self):
        return self.settings.compiler == "clang" and self.settings.arch == "x86"

    # NOTE: host_cpu is not same var as target_cpu
    def append_target_opts(self, opts):
        self.output.info("self.settings.os: %s" % (self.settings.os))

        if self.settings.os == "Linux":
            opts += ['target_os=\\"linux\\"']
            if self.settings.arch == "x86_64":
                opts += ['target_cpu=\\"x64\\"']
            else:
                opts += ['target_cpu=\\"x86\\"']

        # NOTE: requires patch with PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_WIN
        if self.settings.os == "Windows":
            opts += ['target_os=\\"windows\\"']
            if self.settings.arch == "x86_64":
                opts += ['target_cpu=\\"x64\\"']
            else:
                opts += ['target_cpu=\\"x86\\"']

        if self.settings.os == "Macos":
            opts += ['target_os=\\"mac\\"']
            if self.settings.arch == "x86_64":
                opts += ['target_cpu=\\"x64\\"']
            else:
                opts += ['target_cpu=\\"x86\\"']

        # NOTE: requires patch with PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_WASM
        if self.settings.os == "Emscripten" or self.settings.arch == "wasm":
            opts += ['target_os=\\"wasm\\"']
            if self.settings.arch == "x86_64":
                opts += ['target_cpu=\\"x64\\"']
            else:
                opts += ['target_cpu=\\"x86\\"']

        if self.settings.os == "iOS":
            opts += ['target_os=\\"ios\\"']
            if self.settings.arch == "armv8":
                opts += ['target_cpu=\\"arm64\\"']
            else:
                opts += ['target_cpu=\\"x64\\"']

        if self.settings.os == "Android":
            opts += ['target_os=\\"android\\"']
            if self.settings.arch == "armv8":
                opts += ['target_cpu=\\"arm64\\"']
            else:
                opts += ['target_cpu=\\"x64\\"']
        return opts

    @property
    def _cc(self):
        #if "CROSS_COMPILE" in os.environ:
        #    return "gcc"
        if "CC" in os.environ:
            return os.environ["CC"]
        if self.settings.compiler == "apple-clang":
            return tools.XCRun(self.settings).cc #tools.XCRun(self.settings).find("clang")
        elif self.settings.compiler == "clang":
            return "clang"
        elif self.settings.compiler == "gcc":
            return "gcc"
        elif self.settings.compiler == "clang-cl":
            return "clang-cl"
        return "cc"

    def _tool(self, env_name, apple_name):
        if env_name in os.environ:
            return os.environ[env_name]
        if self.settings.compiler == "apple-clang":
            return getattr(tools.XCRun(self.settings), apple_name)
        return None

    def _lib_path_arg(self, path):
        argname = "LIBPATH:" if self.settings.compiler == "Visual Studio" or self._is_clang_cl() else "L"
        return "-{}'{}'".format(argname, path.replace("\\", "/"))

    def build(self):
        # NOTE: CXXFLAGS must match compiler.runtime from conan profile
        # For example, if CXXFLAGS differ, than
        # you may get error: mismatch detected for '_ITERATOR_DEBUG_LEVEL'
        # AutoToolsBuildEnvironment sets LIBS, LDFLAGS, CFLAGS, CXXFLAGS and CPPFLAGS environment variables
        with tools.vcvars(self.settings, only_diff=False): # https://github.com/conan-io/conan/issues/6577
            env_build = AutoToolsBuildEnvironment(self)
            env_build.fpic = self.options.fpic
            with tools.environment_append(env_build.vars):
                self._patch_sources()

                if self.options.get_safe("gen_amalgamated"):
                    self._patch_sources_to_gen_amalgamated()
                    # FIXES: fatal: unsafe repository ('C:/.conan/c543dd/1/source_subfolder' is owned by someone else) 
                    # To add an exception for this directory, call:
                    # git config --global --add safe.directory C:/.conan/c543dd/1/source_subfolder
                    self.run('git config --global --add safe.directory .', cwd=self.build_folder)

                if self.options.warn_no_error:
                    self._patch_sources_to_warn_no_error()

                flags = []

                # TODO
                #for k,v in self.deps_cpp_info.dependencies:
                #    self.output.info("Adding dependency: %s - %s" %(k, v.rootpath))
                #    flags += ['\\"-I%s/include\\"' % (v.rootpath), '\\"-I%s/include/%s\\"' % (v.rootpath, k)]
                
                #cflags = ''
                #cxxflags = ''
                #ldflags = ''
                cflags = (os.environ["CFLAGS"] if "CFLAGS" in os.environ else "")
                cxxflags = (os.environ["CXXFLAGS"] if "CXXFLAGS" in os.environ else "")
                ldflags = (os.environ["LDFLAGS"] if "LDFLAGS" in os.environ else "")
                if self.options.warn_no_error:
                    if self._is_msvc:
                        #cflags = 'extra_cflags=\\"/W0 %s\\"' % (os.environ["CFLAGS"] if "CFLAGS" in os.environ else "")
                        cflags += ' /W0 '
                        cxxflags += ' /W0 '
                    elif self._is_clang_cl:
                        cflags += ' /W0 -Wno-c99-designator -Wno-unused-parameter -Wno-error '
                        cxxflags += ' /W0 -Wno-c99-designator -Wno-unused-parameter -Wno-error '
                    elif self.settings.compiler == "apple-clang" or self.settings.compiler == "clang" or self.settings.compiler == "gcc":
                        cflags += ' -Wno-c99-designator -Wno-unused-parameter -Wno-error '
                        cxxflags += ' -Wno-c99-designator -Wno-unused-parameter -Wno-error '

                #if self.options.get_safe("perfetto_use_system_protobuf"):
                    #cflags += ' -I%s ' % self.deps_cpp_info['protobuf'].cpp_info.includedirs
                    #cxxflags += ' -I%s ' % self.deps_cpp_info['protobuf'].
                
                cflags += ' %s ' % " ".join(self.deps_cpp_info.cflags)

                cxxflags += ' %s ' % " ".join(self.deps_cpp_info.cxxflags) 
                cxxflags += ' %s ' % " ".join("-I'{}'".format(inc.replace("\\", "/")) for inc in self.deps_cpp_info.include_paths)
                cxxflags += ' %s ' % " ".join("-D'{}'".format(inc.replace("\\", "/")) for inc in self.deps_cpp_info.defines)

                ldflags += ' %s ' % " ".join(self.deps_cpp_info.exelinkflags)
                ldflags += ' %s ' % " ".join(self.deps_cpp_info.sharedlinkflags)
                ldflags += ' %s ' % " ".join(self._lib_path_arg(l) for l in self.deps_cpp_info.lib_paths)

                cflags = 'extra_cflags=\\"%s\\"' % cflags
                cxxflags = 'extra_cxxflags=\\"%s\\"' % cxxflags
                ldflags = 'extra_ldflags=\\"%s\\"' % ldflags

                opts = []

                for k,v in self.options.items():
                    if k in self.perfetto_options:
                        opts += [("%s=%s" % (k,v)).lower()]

                # TODO: set (based on conan data) "cc" and "cc_wrapper", but only when use_bundled_compiler=False 
                #compiler_command = os.environ.get('CXX', None)

                self.output.info("self.settings.compiler: %s" % (self.settings.compiler))

                if self.options.append_target_arg:
                    opts = self.append_target_opts(opts)

                ar_opt = ""
                cc_opt = ""
                cxx_opt = ""
                if self.options.get_safe("is_system_compiler"):
                    cc_opt = self._tool("CC", "cc")
                    cxx_opt = self._tool("CXX", "cxx")
                    ar_opt = self._tool("AR", "ar")
                        
                    ar_opt = ('ar=\\"%s\\"' % ar_opt) if (ar_opt is not None and len(ar_opt) and str(ar_opt).lower() != "none") else ""
                    cc_opt = ('cc=\\"%s\\"' % cc_opt) if (cc_opt is not None and len(cc_opt) and str(cc_opt).lower() != "none") else ""
                    cxx_opt = ('cxx=\\"%s\\"' % cxx_opt) if (cxx_opt is not None and len(cxx_opt) and str(cxx_opt).lower() != "none") else ""
                
                #raise errors.ConanInvalidConfiguration("os.environ {} {} {} {}".format(ar_opt, cc_opt, cxx_opt, os.environ))
                
                gn_opts = '"--args=%s %s %s %s %s %s %s"' % (ar_opt, cc_opt, cxx_opt, cflags, cxxflags, ldflags, " ".join(opts))
                self.output.info("gn options: %s" % (gn_opts))

                # Checks that conan options match gn options
                #  --runtime-deps-list-file=runtime-deps.txt
                self.run('gn gen out/conan-build --time -v %s ' %(gn_opts), cwd=self._source_subfolder)

                self.log_gn_options(build_dir="out/conan-build", cwd=self._source_subfolder)

                if self.options.get_safe("check_gn_options"):
                    failed = False
                    failed_options = []
                    for k,v in self.options.items():
                        if k in self.perfetto_options:       
                            actual = self.get_gn_option_value(option_name=k, build_dir="out/conan-build", cwd=self._source_subfolder)
                            if not ("%s" % actual) == ("%s" % v):
                                failed = True
                                failed_options.append("in %s: %s => %s" % ( k, v, actual ))
                                self.output.warn("Mismatch in %s: %s => %s" % ( k, v, actual ))
                    if failed:
                        raise errors.ConanInvalidConfiguration("Final gn configuration did not match requested config for options {}".format(str(failed_options)))
            
                self.run('ninja -C out/conan-build', cwd=self._source_subfolder)

                if not self.options.get_safe("perfetto_use_system_protobuf"):
                    self.run('ninja -C out/conan-build protoc', cwd=self._source_subfolder)

                # ProtoZero is a zero-copy zero-alloc zero-syscall protobuf serialization libary purposefully built for Perfetto's tracing use cases.
                self.run('ninja -C out/conan-build protozero_plugin', cwd=self._source_subfolder)

                if self.options.get_safe("perfetto_unittests"):
                    mybuf = StringIO()
                    try:
                        self.run('out/conan-build/perfetto_unittests --gtest_filter=-*', cwd=self._source_subfolder, output=mybuf)
                    except ConanException:
                        #self.run("gn_unittests", cwd=out_dir_path)
                        self.output.error(mybuf.getvalue())
                        raise

                # TODO: change cflags/ldflags/defines/libs in gen_amalgamated based on cflags/ldflags/defines/libs from env
                if self.options.get_safe("gen_amalgamated"):
                    # Generate the amalgamated source files (sdk/perfetto).
                    python_executable = sys.executable
                    # --gn_args: GN arguments used to prepare the output directory
                    gen_amalgamated_opts = '--gn_args="%s %s %s %s"' % (cflags, cxxflags, ldflags, " ".join(opts))
                    self.output.info("gen_amalgamated options: %s" % (gen_amalgamated_opts))
                    # --dump-deps: List all source files that the amalgamated output depends on
                    # self.run('{python} tools/gen_amalgamated --output sdk/perfetto --dump-deps {opts}'.format(python=python_executable, opts=gen_amalgamated_opts), cwd=self._source_subfolder)
                    if self.options.get_safe("build_gen_amalgamated"):
                        self.run('{python} tools/gen_amalgamated --build --output sdk/perfetto {opts}'.format(python=python_executable, opts=gen_amalgamated_opts), cwd=self._source_subfolder)
                    else:
                        self.run('{python} tools/gen_amalgamated --output sdk/perfetto {opts}'.format(python=python_executable, opts=gen_amalgamated_opts), cwd=self._source_subfolder)

                if self.options.get_safe("build_sdk_examples"):
                    #with tools.chdir(self._source_subfolder):
                    # Check that the SDK example code works with the new release.
                    with tools.vcvars(self.settings, only_diff=False): # https://github.com/conan-io/conan/issues/6577
                        build_subfolder = os.path.join(self.build_folder, self._source_subfolder)
                        cmake = CMake(self)
                        cmake.parallel = True
                        cmake.verbose = True
                        cmake.configure(build_folder=os.path.join(build_subfolder, "examples", "sdk"), source_folder=os.path.join(build_subfolder, "examples", "sdk"), args=['--debug-trycompile'])
                        cpu_count = tools.cpu_count()
                        self.output.info('Detected %s CPUs' % (cpu_count))
                        # -j flag for parallel builds
                        cmake.build(args=["--", "-j%s" % cpu_count])

    def package(self):
        build_subfolder = os.path.join(self.build_folder, self._source_subfolder)
        if not os.path.exists('{}/'.format(build_subfolder)):
            raise errors.ConanInvalidConfiguration('not found: {}/gen'.format(build_subfolder))

        #src_subfolder = os.path.join(self.source_folder, self._source_subfolder)
        src_subfolder = build_subfolder
        if not os.path.exists('{}/sdk'.format(src_subfolder)):
            raise errors.ConanInvalidConfiguration('not found: {}/sdk'.format(src_subfolder))
        if not os.path.exists('{}/protos'.format(src_subfolder)):
            raise errors.ConanInvalidConfiguration('not found: {}/protos'.format(src_subfolder))

        self.copy("LICENSE", dst="licenses", src=src_subfolder)
        self.copy('*', dst='include', src='{}/include'.format(src_subfolder))
        # files generated by protoc
        self.copy("*", dst="gen", src="%s/out/conan-build/gen" % (src_subfolder))
        # NOTE: dont export '/sdk' as public include dir to avoid collisions, 
        # use `perfetto/sdk` instead
        self.copy('*', dst='include/perfetto/sdk', src='{}/sdk'.format(src_subfolder))
        # NOTE: we export `sdk` dir twice because it contains not only header files 
        # i.e. `sdk/perfetto.cc`
        self.copy('*', dst='sdk', src='{}/sdk'.format(src_subfolder))
        # perfetto_trace_protos requires same protobuf version that was used during linking
        # i.e. provide same protobuf headers files
        self.copy('*', dst='buildtools/protobuf', src='{}/buildtools/protobuf'.format(src_subfolder))
        # NOTE: we use `/protos/protos` 
        # due to standard include paths `protos/perfetto/trace/track_event/track_event.proto`
        self.copy('*', dst='protos/protos', src='{}/protos'.format(src_subfolder))
        self.copy("*.dll", dst="bin", src="%s/out/conan-build" % (src_subfolder),keep_path=False)
        self.copy("*.so", dst="lib", src="%s/out/conan-build" % (src_subfolder),keep_path=False)
        self.copy("*.dylib", dst="lib", src="%s/out/conan-build" % (src_subfolder),keep_path=False)
        self.copy("*.a", dst="lib", src="%s/out/conan-build" % (src_subfolder), keep_path=False)
        self.copy("*.lib", dst="lib", src="%s/out/conan-build" % (src_subfolder), keep_path=False)
        # Copy plugins and tools
        self.copy("busy_threads*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("heapprof*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("protoprofile*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("traced*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("idle_alloc*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("cpu_utilization*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("skippy*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("trace_to_text*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("trace_to_text_lite*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("stress_producer*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("cppgen_plugin*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("protozero_plugin*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("perfetto*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("protoc*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("traced_probes*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("compact_reencode*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("ftrace_proto_gen*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("trigger_perfetto*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("traced_perf*", dst="bin", src="%s/out/conan-build" % (src_subfolder))

        # NOTE: The IPC layer based on UNIX sockets can't be built on Win.
        if not self.options.get_safe("enable_perfetto_ipc"):
            self.copy("ipc_plugin*", dst="bin", src="%s/out/conan-build" % (src_subfolder))

        self.copy("dump_ftrace_stats*", dst="bin", src="%s/out/conan-build" % (src_subfolder))
        self.copy("trace_processor_shell*", dst="bin", src="%s/out/conan-build" % (src_subfolder))

    def check_lib_exists(self, libname, folder, lib_prefix, lib_suffix, library_suffixes):
        has_item = False
        arr = []
        for suffix in library_suffixes:
            item = os.path.join(folder, lib_prefix + libname + lib_suffix + suffix)
            arr.append(item)
            if os.path.exists(item):
                has_item = True
                break
        if not has_item:
            raise errors.ConanInvalidConfiguration('not found any of: {}'.format(arr))

    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "perfetto")
        self.cpp_info.set_property("cmake_module_file_name", "perfetto")
        self.cpp_info.set_property("cmake_file_name", "perfetto")
       # self.cpp_info.set_property("pkg_config_name", "perfetto_full_package")

        lib_prefix = "lib" if (self._is_msvc or self._is_clang_cl) else ""
        #lib_suffix = "d" if self.settings.build_type == "Debug" else ""
        lib_suffix = "" # NOTE: without "d"
        library_suffixes = [".lib", ".dll"] if (self._is_msvc or self._is_clang_cl) else [".so", ".dll.a", ".a"]

        self.env_info.LD_LIBRARY_PATH.append(os.path.join(self.package_folder, "lib"))
        self.env_info.PATH.append(os.path.join(self.package_folder, "lib"))
        self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))

        self.cpp_info.components["libperfetto"].names["cmake_find_package"] = "libperfetto"
        self.cpp_info.components["libperfetto"].names["cmake_find_package_multi"] = "libperfetto"
        self.cpp_info.components["libperfetto"].libs = [
            lib_prefix + "perfetto" + lib_suffix,
            "perfetto_trace_protos" + lib_suffix # NOTE: without lib_prefix
            # TODO: lib_prefix + "perfetto_src_tracing_ipc" + lib_suffix
            # TODO: lib_prefix + "libperfetto_android_internal" + lib_suffix
        ]
        self.check_lib_exists("perfetto", os.path.join(self.package_folder, "lib"), lib_prefix, lib_suffix, library_suffixes)
        self.check_lib_exists("perfetto_trace_protos", os.path.join(self.package_folder, "lib"), "", lib_suffix, library_suffixes) # NOTE: without lib_prefix
        self.cpp_info.components["libperfetto"].includedirs = [
            os.path.join(self.package_folder),
            os.path.join(self.package_folder, "sdk"),
            os.path.join(self.package_folder, "include")
        ]
        self.cpp_info.components["libperfetto"].libdirs = [os.path.join(self.package_folder, "lib")]
        self.cpp_info.components["libperfetto"].bindirs = [os.path.join(self.package_folder, "bin")]
        self.cpp_info.components["libperfetto"].defines += ["CONAN_PERFETTO=1"]
        if self.settings.os == "Windows":
            self.cpp_info.components["libperfetto"].system_libs.append("wsock32")
            self.cpp_info.components["libperfetto"].system_libs.append("ws2_32")
        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.components["libperfetto"].system_libs.append("pthread")
            if self._is_clang_x86 or "arm" in str(self.settings.arch):
                self.cpp_info.components["libperfetto"].system_libs.append("atomic")
            if self.settings.os == "Windows":
                if self.options.shared:
                    self.cpp_info.components["libperfetto"].defines = ["PROTOBUF_USE_DLLS"]
            if self.settings.os == "Android":
                self.cpp_info.components["libperfetto"].system_libs.append("log")

        # The SDK consists of two files, sdk/perfetto.h and sdk/perfetto.cc. These are an amalgamation of the Client API designed to easy to integrate to existing build systems. The sources are self-contained and require only a C++11 compliant standard library.
        self.cpp_info.components["perfetto-sdk"].names["cmake_find_package"] = "perfetto-sdk"
        self.cpp_info.components["perfetto-sdk"].names["cmake_find_package_multi"] = "perfetto-sdk"
        self.cpp_info.components["perfetto-sdk"].names["pkg_config"] = "perfetto-sdk"
        self.cpp_info.components["perfetto-sdk"].bindirs = [os.path.join(self.package_folder, "bin")]
        self.cpp_info.components["perfetto-sdk"].includedirs = [
            os.path.join(self.package_folder),
            os.path.join(self.package_folder, "sdk"),
        ]

        self.cpp_info.components["perfetto-gen"].names["cmake_find_package"] = "perfetto-gen"
        self.cpp_info.components["perfetto-gen"].names["cmake_find_package_multi"] = "perfetto-gen"
        self.cpp_info.components["perfetto-gen"].names["pkg_config"] = "perfetto-gen"
        self.cpp_info.components["perfetto-gen"].bindirs = [os.path.join(self.package_folder, "bin")]
        self.cpp_info.components["perfetto-gen"].includedirs = [
            os.path.join(self.package_folder, "gen"),
        ]

        self.cpp_info.components["perfetto-buildtools"].names["cmake_find_package"] = "perfetto-buildtools"
        self.cpp_info.components["perfetto-buildtools"].names["cmake_find_package_multi"] = "perfetto-buildtools"
        self.cpp_info.components["perfetto-buildtools"].names["pkg_config"] = "perfetto-buildtools"
        self.cpp_info.components["perfetto-buildtools"].bindirs = [os.path.join(self.package_folder, "bin")]
        self.cpp_info.components["perfetto-buildtools"].includedirs = [
            os.path.join(self.package_folder, "buildtools"),
        ]

        self.cpp_info.components["perfetto-protos"].names["cmake_find_package"] = "perfetto-protos"
        self.cpp_info.components["perfetto-protos"].names["cmake_find_package_multi"] = "perfetto-protos"
        self.cpp_info.components["perfetto-protos"].names["pkg_config"] = "perfetto-protos"
        self.cpp_info.components["perfetto-protos"].bindirs = [os.path.join(self.package_folder, "bin")]
        self.cpp_info.components["perfetto-protos"].includedirs = [
            os.path.join(self.package_folder, "protos"),
        ]

        self.cpp_info.components["perfetto-protoc"].names["cmake_find_package"] = "perfetto-protoc"
        self.cpp_info.components["perfetto-protoc"].names["cmake_find_package_multi"] = "perfetto-protoc"
        self.cpp_info.components["perfetto-protoc"].names["pkg_config"] = "perfetto-protoc"
        self.cpp_info.components["perfetto-protoc"].bindirs = [os.path.join(self.package_folder, "bin")]

        self.cpp_info.components["perfetto-protozero-plugin"].names["cmake_find_package"] = "perfetto-protozero-plugin"
        self.cpp_info.components["perfetto-protozero-plugin"].names["cmake_find_package_multi"] = "perfetto-protozero-plugin"
        self.cpp_info.components["perfetto-protozero-plugin"].names["pkg_config"] = "perfetto-protozero-plugin"
        self.cpp_info.components["perfetto-protozero-plugin"].bindirs = [os.path.join(self.package_folder, "bin")]

        self.cpp_info.components["perfetto-cppgen-plugin"].names["cmake_find_package"] = "perfetto-cppgen-plugin"
        self.cpp_info.components["perfetto-cppgen-plugin"].names["cmake_find_package_multi"] = "perfetto-cppgen-plugin"
        self.cpp_info.components["perfetto-cppgen-plugin"].names["pkg_config"] = "perfetto-cppgen-plugin"
        self.cpp_info.components["perfetto-cppgen-plugin"].bindirs = [os.path.join(self.package_folder, "bin")]

        self.cpp_info.components["perfetto-ipc-plugin"].names["cmake_find_package"] = "perfetto-ipc-plugin"
        self.cpp_info.components["perfetto-ipc-plugin"].names["cmake_find_package_multi"] = "perfetto-ipc-plugin"
        self.cpp_info.components["perfetto-ipc-plugin"].names["pkg_config"] = "perfetto-ipc-plugin"
        self.cpp_info.components["perfetto-ipc-plugin"].bindirs = [os.path.join(self.package_folder, "bin")]

        #protoc = "protoc.exe" if self.settings.os_build == "Windows" else "protoc"
        #self.env_info.PERFETTO_PROTOC_BIN = os.path.normpath(os.path.join(self.package_folder, "bin", protoc))
        #self.user_info.PERFETTO_PROTOC_BIN = self.env_info.PERFETTO_PROTOC_BIN
        #
        #protozero_plugin = "protozero_plugin.exe" if self.settings.os_build == "Windows" else "protozero_plugin"
        #self.env_info.PERFETTO_protozero_plugin_BIN = os.path.normpath(os.path.join(self.package_folder, "bin", protozero_plugin))
        #self.user_info.PERFETTO_protozero_plugin_BIN = self.env_info.PERFETTO_protozero_plugin_BIN
        #
        #cppgen_plugin = "cppgen_plugin.exe" if self.settings.os_build == "Windows" else "cppgen_plugin"
        #self.env_info.PERFETTO_cppgen_plugin_BIN = os.path.normpath(os.path.join(self.package_folder, "bin", cppgen_plugin))
        #self.user_info.PERFETTO_cppgen_plugin_BIN = self.env_info.PERFETTO_cppgen_plugin_BIN
        #
        # NOTE: The IPC layer based on UNIX sockets can't be built on Win.
        #if not self.options.get_safe("enable_perfetto_ipc"):
        #    ipc_plugin = "ipc_plugin.exe" if self.settings.os_build == "Windows" else "ipc_plugin"
        #    self.env_info.PERFETTO_ipc_plugin_BIN = os.path.normpath(os.path.join(self.package_folder, "bin", ipc_plugin))
        #    self.user_info.PERFETTO_ipc_plugin_BIN = self.env_info.PERFETTO_ipc_plugin_BIN
        #
        # must contain `protobuf/src/google/protobuf/port_def.inc`
        #self.env_info.PERFETTO_BUILDTOOLS_DIR = os.path.normpath(os.path.join(self.package_folder, "buildtools"))
        #self.user_info.PERFETTO_BUILDTOOLS_DIR = self.env_info.PERFETTO_BUILDTOOLS_DIR
        #
        # must contain `perfetto.cc`
        #self.env_info.PERFETTO_SDK_DIR = os.path.normpath(os.path.join(self.package_folder, "sdk"))
        #self.user_info.PERFETTO_SDK_DIR = self.env_info.PERFETTO_SDK_DIR
        #
        # must contain `protos/perfetto/trace/track_event/track_event.pbzero.h`
        #self.env_info.PERFETTO_GEN_DIR = os.path.normpath(os.path.join(self.package_folder, "gen"))
        #self.user_info.PERFETTO_GEN_DIR = self.env_info.PERFETTO_GEN_DIR
        #
        # must contain `perfetto/trace/track_event/track_event.proto`
        #self.env_info.PERFETTO_PROTOS_DIR = os.path.normpath(os.path.join(self.package_folder, "protos"))
        #self.user_info.PERFETTO_PROTOS_DIR = self.env_info.PERFETTO_PROTOS_DIR

