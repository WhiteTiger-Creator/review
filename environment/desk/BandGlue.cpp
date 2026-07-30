#include "SpliceBand.hpp"
#include <string>

std::string bind_line_local(const std::string& graph_id, int depth) {
  return splice_band_v(graph_id, depth);
}
