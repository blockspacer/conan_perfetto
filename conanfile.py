import os, re, stat, json, fnmatch, platform, glob, traceback, shutil
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
    version = "v13.0"
    url = "https://github.com/google/perfetto"

    license = "MIT"

    exports_sources = ["CMakeLists.txt", "patches/**"]
    short_paths = True

    settings = "os", "arch", "compiler", "build_type"

    perfetto_options = {
        "is_debug" : [True, False],
        "is_clang" : [True, False],
        "is_hermetic_clang" : [True, False],
        "is_asan" : [True, False],
        "is_lsan" : [True, False],
        "is_msan" : [True, False],
        "is_tsan" : [True, False],
        "is_ubsan" : [True, False],
    }

    options = merge_two_dicts({ "use_bundled_compiler": [True, False] }, perfetto_options)

    default_options = {
        "use_bundled_compiler":False,
        # perfetto options
        "is_debug" : False,
        "is_clang" : False,
        "is_hermetic_clang" : False,
        "is_asan" : False,
        "is_lsan" : False,
        "is_msan" : False,
        "is_tsan" : False,
        "is_ubsan" : False
    }

    generators = "cmake"
    build_policy = "missing"

    _cmake = None

    def get_gn_option_value(self, option_name, build_dir, cwd):
        buf = StringIO()
        self.run('gn args %s --list=%s --short' % (build_dir, option_name), output=buf, cwd=cwd)
        output = buf.getvalue()
        self.output.info("output - %s" %(output))
        pattern = r'%s = (.*)' % (option_name)
        for str in re.findall(pattern,output):
            self.output.info("str - %s" %(str))
            if str == 'true':
                return True
            elif str == 'false':
                return False

        raise errors.ConanInvalidConfiguration("Could not parse gn configuration options because option {} not found in {} due to match {}".format(option_name, output, match))

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    def configure(self):
        if self.settings.compiler.cppstd:
            tools.check_min_cppstd(self, 11)

        lower_build_type = str(self.settings.build_type).lower()

    def build_requirements(self):
        self.build_requires("cmake_platform_detection/master@conan/stable")
        self.build_requires("cmake_build_options/master@conan/stable")
        self.build_requires("cmake_helper_utils/master@conan/stable")
        self.build_requires("google_gn/master@conan/stable")
        self.build_requires("ninja_installer/1.9.0@bincrafters/stable")
        self.build_requires("cmake_installer/3.15.5@conan/stable")

    def source(self):
        self.run('git clone -b {} --progress --depth 100 --recursive --recurse-submodules {} {}'.format(self.version, self.repo_url, self._source_subfolder))
        with tools.chdir(self._source_subfolder):
            self.run('tools/install-build-deps')

    def build(self):
        opts = []

        # TODO
        #flags = []
        #for k,v in self.deps_cpp_info.dependencies:
        #    self.output.info("Adding dependency: %s - %s" %(k, v.rootpath))
        #    flags += ['\\"-I%s/include\\"' % (v.rootpath), '\\"-I%s/include/%s\\"' % (v.rootpath, k)]
        #flag_str = 'extra_cflags_cc=[%s]' % ",".join(flags)
        #opts = [flag_str]

        for k,v in self.options.items():
            if k in self.perfetto_options:
                opts += [("%s=%s" % (k,v)).lower()]

        # TODO
        #compiler_command = os.environ.get('CXX', None)
        #cc = "gcc"
        #cxx = "g++"

        if self.settings.build_type == "Debug":
            opts += ["is_debug=true"]
        else:
            opts += ["is_debug=false"]

        self.output.info("self.settings.compiler: %s" % (self.settings.compiler))

        if not self.options.use_bundled_compiler:
            if self.settings.compiler == "apple-clang" or self.settings.compiler == "clang" or self.settings.compiler == "clang-cl":
                opts += ["is_clang=true"]
                if not self.options.is_clang:
                    raise errors.ConanInvalidConfiguration("build with -o is_clang=true")
            else:
                opts += ["is_clang=false"]

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

        if len(opts) > 0:
            opts = '"--args=%s"' % " ".join(opts)
        else:
            opts = ""

        self.output.info("gn options: %s" % (opts))

        # Checks that conan options match gn options
        self.run('gn gen out/conan-build %s ' %(opts), cwd=self._source_subfolder)
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

    def package(self):
        self.copy("LICENSE", dst="licenses", src=self._source_subfolder)
        self.copy("*.h", dst="include/perfetto", src=self._source_subfolder, keep_path=True)
        self.copy("*.dll", dst="bin", src="perfetto/out/conan-build",keep_path=False)
        self.copy("*.so", dst="lib", src="perfetto/out/conan-build",keep_path=False)
        self.copy("*.dylib", dst="lib", src="perfetto/out/conan-build",keep_path=False)
        self.copy("*.a", dst="lib", src="perfetto/out/conan-build", keep_path=False)

    def package_info(self):
        self.cpp_info.names["cmake_find_package"] = "perfetto"
        self.cpp_info.names["cmake_find_package_multi"] = "perfetto"

        libs = os.listdir(os.path.join(self.package_folder, "lib"))
        libs = [(x[3:])[:-2] for x in libs]


