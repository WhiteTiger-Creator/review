#pragma once

#include "model/record.h"

#include <string>

namespace site {

Record decode_record(const std::string& text);
std::string encode_record(const Record& record);

}  // namespace site
