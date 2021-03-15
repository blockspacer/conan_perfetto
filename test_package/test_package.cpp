#include <string>
#include <utility>
#include <iostream>
#include <vector>

#include <perfetto/sdk/perfetto.h>

#include "perfetto_build_flags.h"

#include "chrome_track_event.pbzero.h"

int main()
{
  perfetto::TracingInitArgs args;

  // The backends determine where trace events are recorded. You may select one
  // or more of:

  // 1) The in-process backend only records within the app itself.
  args.backends |= perfetto::kInProcessBackend;

  // 2) The system backend writes events into a system Perfetto daemon,
  //    allowing merging app and system events (e.g., ftrace) on the same
  //    timeline. Requires the Perfetto `traced` daemon to be running (e.g.,
  //    on Android Pie and newer).
  args.backends |= perfetto::kSystemBackend;

  perfetto::Tracing::Initialize(args);
}
