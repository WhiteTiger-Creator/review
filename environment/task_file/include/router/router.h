#pragma once

#include <string>

#include "route.grpc.pb.h"
#include "route.pb.h"

namespace router {

struct Summary {
  std::string id;
  std::string build_mode;
  std::string path;
  unsigned checksum;
};

Summary summarize(const routekit::v1::RouteJob& job);
std::string render(const Summary& summary);
const char* expected_mode();

}  // namespace router
