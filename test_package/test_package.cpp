#include <string>
#include <utility>
#include <iostream>
#include <sstream>
#include <chrono>
#include <fstream>
#include <thread>
#include <vector>
#include <cstdlib>
#include <codecvt>
#include <random>

#include <sys/stat.h>
#include <fcntl.h>
#ifdef _WIN32
# define SEPARATOR "\\"
# include <io.h>
# include <windows.h>
#else
# define SEPARATOR "/"
#include <unistd.h>
#endif

#include <sdk/perfetto.h>

#include "perfetto_build_flags.h"

#include "chrome_track_event.pbzero.h"

PERFETTO_DEFINE_CATEGORIES(
    perfetto::Category("category")
        .SetDescription("Events from the category subsystem"),
    perfetto::Category("rendering")
        .SetDescription("Events from the graphics subsystem"),
    perfetto::Category("network")
        .SetDescription("Network upload and download statistics"),
    perfetto::Category("PictureLayer::Update").SetTags("debug")
      .SetDescription("PictureLayer::Update events"),
    perfetto::Category("nodejs.something").SetTags("debug")
      .SetDescription("nodejs.something events"),
    perfetto::Category("gpu.debug").SetTags("debug")
      .SetDescription("debug gpu events"),
    perfetto::Category("audio.latency").SetTags("verbose")
      .SetDescription("Detailed audio latency metrics"));

/*PERFETTO_DEFINE_CATEGORIES(
    perfetto::Category("rendering")
        .SetDescription("Rendering and graphics events"),
    perfetto::Category("network.debug")
        .SetTags("debug")
        .SetDescription("Verbose network events"),
    perfetto::Category("audio.latency")
        .SetTags("verbose")
        .SetDescription("Detailed audio latency metrics"));*/

// Some trace categories are only useful for testing, 
// and they should not make it into a production binary. 
// These types of categories can be defined with a list of prefix strings:
PERFETTO_DEFINE_TEST_CATEGORY_PREFIXES(
   "test",      // Applies to test.*
   "dontship"   // Applies to dontship.*.
);

class CustomDataSource : public perfetto::DataSource<CustomDataSource> {
 public:
  void OnSetup(const SetupArgs&) override {
    // Use this callback to apply any custom configuration to your data source
    // based on the TraceConfig in SetupArgs.
  }

  void OnStart(const StartArgs&) override {
    // This notification can be used to initialize the GPU driver, enable
    // counters, etc. StartArgs will contains the DataSourceDescriptor,
    // which can be extended.
  }

  void OnStop(const StopArgs&) override {
    // Undo any initialization done in OnStart.
  }

  // Data sources can also have per-instance state.
  int my_custom_state = 0;
};

PERFETTO_DECLARE_DATA_SOURCE_STATIC_MEMBERS(CustomDataSource);

PERFETTO_DEFINE_DATA_SOURCE_STATIC_MEMBERS(CustomDataSource);

// Reserves internal static storage for our tracing categories.
PERFETTO_TRACK_EVENT_STATIC_STORAGE();

static void DrawWeapons(int PlayerNum, int WeaponNum)
{
  TRACE_EVENT("rendering", "DrawWeapons", "WeaponNum", WeaponNum, "PlayerNum", PlayerNum);
  std::this_thread::sleep_for(std::chrono::milliseconds(200));
}

static void DrawPlayer(int player_number, int weapon_num) 
{
  TRACE_EVENT("rendering", "DrawPlayer", "player_number", player_number);
  // Sleep to simulate a long computation.
  std::this_thread::sleep_for(std::chrono::milliseconds(500));
  DrawWeapons(player_number, weapon_num);
}

static void DrawGame() {
  // This is an example of an unscoped slice, which begins and ends at specific
  // points (instead of at the end of the current block scope).
  TRACE_EVENT_BEGIN("rendering", "DrawGame");
  //const char* name = "DrawGame";
  //TRACE_EVENT_BEGIN("rendering", name);
  DrawPlayer(1, 3);
  DrawPlayer(2, 4);
  TRACE_EVENT_END("rendering");

  // Record the rendering framerate as a counter sample.
  TRACE_COUNTER("rendering", "Framerate", 120);
}

static std::unique_ptr<std::thread> worker_thread;

static constexpr int process_id = 12345;
static constexpr int thread_id = 423432;
static constexpr int track_id = 53478;
static const std::string processName = "example_process";
static const std::string threadName = "example_thread";

void OnNewRequest(size_t request_id) {
  // Open a slice when the request came in.
  TRACE_EVENT_BEGIN("category", "HandleRequest", perfetto::Track(track_id));

  // Start a thread to handle the request.
  worker_thread = std::make_unique<std::thread>([=] {
    perfetto::ThreadTrack thread_track  = perfetto::ThreadTrack::Current();
    perfetto::protos::gen::TrackDescriptor desc = thread_track.Serialize();
    desc.mutable_thread()->set_pid(thread_id);
    desc.mutable_thread()->set_thread_name(threadName.c_str());
    perfetto::TrackEvent::SetTrackDescriptor(thread_track , std::move(desc));

    // ... produce response ...
    std::this_thread::sleep_for(std::chrono::milliseconds(std::min(1000, (int)(request_id*50))));

    // Close the slice for the request now that we finished handling it.
    TRACE_EVENT_END("category", perfetto::Track(request_id));
  });
}

static void OnPerfettoLogMessage(perfetto::base::LogMessageCallbackArgs args) {
  // Perfetto levels start at 0, base's at -1.
  int severity = static_cast<int>(args.level) - 1;
  std::cout << args.filename << "[" << args.line << ":" << severity << "]:" << args.message;
}

// see https://github.com/google/perfetto/tree/master/examples/sdk
// see https://reviews.llvm.org/D82994?id=286866
int main()
{
  perfetto::TracingInitArgs args;

  // The backends determine where trace events are recorded. You may select one
  // or more of:
  // 1) The in-process backend only records within the app itself.
  //    args.backends |= perfetto::kInProcessBackend;
  // 2) The system backend writes events into a system Perfetto daemon,
  //    allowing merging app and system events (e.g., ftrace) on the same
  //    timeline. Requires the Perfetto `traced` daemon to be running (e.g.,
  //    on Android Pie and newer).
  //    args.backends |= perfetto::kSystemBackend;
  args.backends |= perfetto::kInProcessBackend;

  // Proxy perfetto log messages into logs, so they are retained on all
  // platforms. In particular, on Windows, Perfetto's stderr log messages are
  // not reliable.
  args.log_message_callback = &OnPerfettoLogMessage;

  perfetto::Tracing::Initialize(args);

  /*perfetto::DataSourceDescriptor dsd;
  dsd.set_name("com.example.custom_data_source");
  CustomDataSource::Register(dsd);*/

  /*perfetto::protos::gen::TrackEventConfig track_event_cfg;
  track_event_cfg.add_disabled_categories("*");
  track_event_cfg.add_enabled_categories("rendering");*/

  perfetto::TrackEvent::Register();

  perfetto::TraceConfig cfg;
  cfg.add_buffers()->set_size_kb(1024);
  auto* ds_cfg = cfg.add_data_sources()->mutable_config();
  ds_cfg->set_name("track_event");
  //perfetto_config.mutable_incremental_state_config()->set_clear_period_ms(
  //  config->interning_reset_interval_ms());

  /*cfg.set_duration_ms(5*60*1000);
  cfg.add_buffers()->set_size_kb(5*1024);*/

  /*auto* ds_cfg = cfg.add_data_sources()->mutable_config();
  ds_cfg->set_name("com.example.custom_data_source");
  ds_cfg->set_track_event_config_raw(track_event_cfg.SerializeAsString());*/

  std::unique_ptr<perfetto::TracingSession> tracing_session(
      perfetto::Tracing::NewTrace(perfetto::kInProcessBackend));
  
  int memory_fd = -1;
/*
  const std::string fullpath = "memory.pftrace";
#ifdef _WIN32
  std::wstring_convert<std::codecvt_utf8_utf16<wchar_t>> converter;
  std::wstring wpath = converter.from_bytes(fullpath);
  memory_fd = _wopen(wpath.c_str(), O_RDWR | O_CREAT | O_TRUNC, S_IWRITE);
#else
  memory_fd = open(fullpath.c_str(), O_RDWR | O_CREAT | O_TRUNC, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
#endif
  if (memory_fd == -1) {
      return EXIT_FAILURE;
  }
  // To save memory with longer traces, you can also tell Perfetto to write directly into a file
  // NOTE: Passing a file descriptor to TracingSession::Setup() is only supported 
  // with the kInProcessBackend on Windows. Use TracingSession::ReadTrace() instead
  tracing_session->Setup(cfg, memory_fd);*/

  tracing_session->Setup(cfg);

  tracing_session->StartBlocking();

  // Give a custom name for the traced process.
  /*perfetto::ProcessTrack process_track = perfetto::ProcessTrack::Current();
  perfetto::protos::gen::TrackDescriptor desc = process_track.Serialize();
  desc.mutable_process()->set_process_name("Example");
  perfetto::TrackEvent::SetTrackDescriptor(process_track, desc);*/

  perfetto::ProcessTrack process_track = perfetto::ProcessTrack::Current();
  perfetto::protos::gen::TrackDescriptor desc = process_track.Serialize();
  desc.mutable_process()->set_pid(process_id);
  desc.mutable_process()->set_process_name(processName.c_str());
  perfetto::TrackEvent::SetTrackDescriptor(process_track, std::move(desc));

  //perfetto::DynamicCategory dynamic_category{"nodejs.something"};
  //TRACE_EVENT(dynamic_category, "SomeEvent");

  std::this_thread::sleep_for(std::chrono::milliseconds(100));
  
  std::string dynamic_name = "PictureLayer::Update";
  TRACE_EVENT("rendering", perfetto::DynamicString{dynamic_name});

  std::random_device rd;  //Will be used to obtain a seed for the random number engine
  std::mt19937 gen(rd()); //Standard mersenne_twister_engine seeded with rd()
  std::uniform_int_distribution<> distrib(1, 6);

  auto i = distrib(gen);

  OnNewRequest(i);

  const char* name1 = "DrawGame1";
  const char* name2 = "DrawGame2";
  const char* namePtr = i % 2 == 0 ? name1 : name2;
  TRACE_EVENT("rendering", perfetto::StaticString{namePtr});

  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  TRACE_EVENT("network", "MyEvent", "parameter", 42);

  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  /*CustomDataSource::Trace([](CustomDataSource::TraceContext ctx) {
    auto packet = ctx.NewTracePacket();
    packet->set_timestamp(perfetto::TrackEvent::GetTraceTimeNs());
    packet->set_for_testing()->set_str("Hello world!");
  });

  std::this_thread::sleep_for(std::chrono::milliseconds(100));*/

  // Simulate some work that emits trace events.
  DrawGame();

  if (worker_thread) {
    worker_thread->join();
  }
  
  perfetto::TrackEvent::Flush();
  tracing_session->StopBlocking();

  std::vector<char> trace_data(tracing_session->ReadTraceBlocking());
  if (!trace_data.empty()) {
    // Write the trace into a file.
    std::ofstream output;
    output.open("example3.pftrace", std::ios::out | std::ios::binary);
    output.write(&trace_data[0], std::streamsize(trace_data.size()));
    output.close();
    if (memory_fd != -1) {
      close(memory_fd);
    }
  }
  
  return EXIT_SUCCESS;
}
