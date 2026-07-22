#include "router/router.h"

#include <cstdint>
#include <sstream>
#include <string>

#ifndef ROUTER_BUILD_MODE
#define ROUTER_BUILD_MODE "unknown"
#endif

namespace router {
namespace {

uint32_t mix(uint32_t state, const std::string& text) {
  for (unsigned char ch : text) {
    state ^= ch;
    state *= 16777619u;
  }
  return state;
}

}  // namespace

const char* expected_mode() { return ROUTER_BUILD_MODE; }

Summary summarize(const routekit::v1::RouteJob& job) {
  (void)routekit::v1::RouteBroker::service_full_name();

  std::ostringstream path;
  for (int i = 0; i < job.hops_size(); ++i) {
    if (i != 0) {
      path << "->";
    }
    path << job.hops(i);
  }

  uint32_t checksum = 2166136261u;
  checksum = mix(checksum, job.id());
  checksum = mix(checksum, job.payload());
  for (const auto& hop : job.hops()) {
    checksum = mix(checksum, hop);
  }
  checksum ^= job.priority();
  checksum &= 0xffffu;

  return Summary{job.id(), expected_mode(), path.str(), checksum};
}

std::string render(const Summary& summary) {
  std::ostringstream out;
  out << summary.id << '|' << summary.build_mode << '|' << summary.path << '|'
      << summary.checksum;
  return out.str();
}

}  // namespace router
