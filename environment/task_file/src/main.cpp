#include "router/router.h"

#include <dlfcn.h>

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

using AuditAccepts = int (*)(const char*, const char*);

std::filesystem::path default_plugin_path(const char* argv0) {
  std::filesystem::path exe = std::filesystem::weakly_canonical(argv0);
  return exe.parent_path().parent_path() / "lib" / "route" / "libroute_audit.so";
}

std::string require_value(int& index, int argc, char** argv) {
  if (index + 1 >= argc) {
    throw std::runtime_error(std::string("missing value for ") + argv[index]);
  }
  ++index;
  return argv[index];
}

}  // namespace

int main(int argc, char** argv) {
  routekit::v1::RouteJob job;
  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg == "--id") {
      job.set_id(require_value(i, argc, argv));
    } else if (arg == "--payload") {
      job.set_payload(require_value(i, argc, argv));
    } else if (arg == "--hop") {
      job.add_hops(require_value(i, argc, argv));
    } else if (arg == "--priority") {
      job.set_priority(static_cast<unsigned>(std::stoul(require_value(i, argc, argv))));
    } else {
      std::cerr << "unknown argument: " << arg << '\n';
      return 2;
    }
  }

  if (job.id().empty() || job.hops_size() == 0) {
    std::cerr << "route id and at least one hop are required\n";
    return 2;
  }

  auto summary = router::summarize(job);
  auto plugin_path = default_plugin_path(argv[0]);
  void* handle = dlopen(plugin_path.c_str(), RTLD_NOW);
  if (handle == nullptr) {
    std::cerr << "could not load audit plugin: " << dlerror() << '\n';
    return 3;
  }
  auto* accepts = reinterpret_cast<AuditAccepts>(dlsym(handle, "routekit_audit_accepts"));
  if (accepts == nullptr || accepts(summary.id.c_str(), summary.build_mode.c_str()) != 1) {
    std::cerr << "audit plugin rejected route summary\n";
    dlclose(handle);
    return 4;
  }

  std::cout << router::render(summary) << '\n';
  dlclose(handle);
  return 0;
}
