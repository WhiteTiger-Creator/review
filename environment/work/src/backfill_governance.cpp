#include <fstream>
#include <iostream>
#include <map>
#include <string>

static std::map<std::string, std::string> load(const std::string& path) {
    std::ifstream input(path);
    std::map<std::string, std::string> values;
    std::string line;
    while (std::getline(input, line)) {
        const auto split = line.find('=');
        if (split != std::string::npos) {
            values[line.substr(0, split)] = line.substr(split + 1);
        }
    }
    return values;
}

int main(int argc, char** argv) {
    if (argc != 2) {
        return 64;
    }
    const auto state = load(argv[1]);
    if (!state.contains("observed_epoch")) {
        return 65;
    }
    std::cout << "epoch " << state.at("observed_epoch") << '\n';
    std::cout << "hold conservative-starter\n";
    std::cout << "publish paused\n";
    return 0;
}
