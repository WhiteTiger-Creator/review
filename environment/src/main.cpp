#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

namespace {

struct Row {
    std::vector<int> features;
    int label = 0;
};

using Table = std::vector<Row>;

std::map<std::string, Table> read_tables(const std::string& directory) {
    std::map<std::string, Table> out;
    std::vector<std::string> names;
    for (const auto& entry : std::filesystem::directory_iterator(directory)) {
        std::string name = entry.path().filename().string();
        if (name.size() > 4 && name.substr(name.size() - 4) == ".csv") {
            names.push_back(name);
        }
    }
    std::sort(names.begin(), names.end());
    for (const std::string& name : names) {
        std::ifstream in(directory + "/" + name);
        std::string line;
        Table rows;
        bool header = true;
        while (std::getline(in, line)) {
            while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) {
                line.pop_back();
            }
            if (line.empty()) {
                continue;
            }
            if (header) {
                header = false;
                continue;
            }
            std::vector<int> cells;
            std::stringstream ss(line);
            std::string cell;
            while (std::getline(ss, cell, ',')) {
                cells.push_back(std::stoi(cell));
            }
            Row row;
            row.label = cells.back();
            cells.pop_back();
            row.features = cells;
            rows.push_back(row);
        }
        out[name.substr(0, name.size() - 4)] = rows;
    }
    return out;
}

std::vector<std::string> report(const std::map<std::string, Table>& tables,
                                const std::vector<std::string>& parts) {
    (void)tables;
    (void)parts;
    return {};
}

}

int main(int argc, char** argv) {
    if (argc < 3) {
        return 1;
    }
    std::map<std::string, Table> tables = read_tables(argv[1]);
    std::ifstream queries(argv[2]);
    std::string line;
    std::string out;
    while (std::getline(queries, line)) {
        std::stringstream ss(line);
        std::vector<std::string> parts;
        std::string token;
        while (ss >> token) {
            parts.push_back(token);
        }
        if (parts.empty()) {
            continue;
        }
        for (const std::string& row : report(tables, parts)) {
            out += row;
            out += "\n";
        }
    }
    std::cout << out;
    return 0;
}
