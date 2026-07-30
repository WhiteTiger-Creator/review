#include <string>
#include <sstream>

// pretty-print headers for human diffs and smoke banners
std::string pretty_band_header(const std::string& graph_id) {
  std::ostringstream oss;
  oss << "HDR:" << graph_id;
  return oss.str();
}

std::string pretty_band_banner(const std::string& graph_id, int depth) {
  std::ostringstream oss;
  oss << pretty_band_header(graph_id) << "|depth=" << depth;
  return oss.str();
}
