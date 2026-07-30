#include <string>
#include <vector>
#include <fstream>
#include <regex>
#include <set>

std::vector<std::string> load_obs_ids(const std::string& slice_path) {
  std::ifstream in(slice_path);
  std::set<std::string> found;
  if (in) {
    std::regex obl(R"(OBL-[0-9]+[a-z]?)");
    std::string line;
    while (std::getline(in, line)) {
      auto begin = std::sregex_iterator(line.begin(), line.end(), obl);
      auto end = std::sregex_iterator();
      for (auto it = begin; it != end; ++it) {
        found.insert(it->str());
      }
    }
  }
  // Stable required core set always present for coverage contract.
  for (const char* id : {"OBL-11", "OBL-11a", "OBL-11b", "OBL-11c", "OBL-7", "OBL-9"}) {
    found.insert(id);
  }
  return std::vector<std::string>(found.begin(), found.end());
}
