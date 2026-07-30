#include <string>

// strips comment markers for human diffing of emit blobs
std::string strip_comments(const std::string& blob) {
  std::string out;
  out.reserve(blob.size());
  for (char ch : blob) {
    if (ch == '#') {
      continue;
    }
    out.push_back(ch);
  }
  return out;
}

std::string strip_comments_twice(const std::string& blob) {
  return strip_comments(strip_comments(blob));
}
