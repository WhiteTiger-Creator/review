#include <sqlite3.h>
#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
std::string trim(std::string value) {
    while (!value.empty() && std::isspace(static_cast<unsigned char>(value.front()))) value.erase(value.begin());
    while (!value.empty() && std::isspace(static_cast<unsigned char>(value.back()))) value.pop_back();
    return value;
}

bool allowed(const std::string& sql) {
    std::string lower = trim(sql);
    std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (lower.empty() || lower.find(';') != std::string::npos) return false;
    if (!(lower.rfind("select", 0) == 0 || lower.rfind("with", 0) == 0 || lower.rfind("pragma table_info", 0) == 0)) return false;
    for (const auto& forbidden : {" attach ", " detach ", " load_extension(", "pragma writable_schema", "pragma journal_mode"}) {
        if ((" " + lower + " ").find(forbidden) != std::string::npos) return false;
    }
    return true;
}

void emit_statement(sqlite3* db, const std::string& sql) {
    if (!allowed(sql)) throw std::runtime_error("statement rejected");
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) throw std::runtime_error(sqlite3_errmsg(db));
    const int columns = sqlite3_column_count(stmt);
    if (columns <= 0) {
        sqlite3_finalize(stmt);
        throw std::runtime_error("statement returned no columns");
    }
    for (int i = 0; i < columns; ++i) {
        if (i) std::cout << '\t';
        std::cout << sqlite3_column_name(stmt, i);
    }
    std::cout << '\n';
    while (true) {
        const int rc = sqlite3_step(stmt);
        if (rc == SQLITE_DONE) break;
        if (rc != SQLITE_ROW) {
            const std::string message = sqlite3_errmsg(db);
            sqlite3_finalize(stmt);
            throw std::runtime_error(message);
        }
        for (int i = 0; i < columns; ++i) {
            if (i) std::cout << '\t';
            const unsigned char* text = sqlite3_column_text(stmt, i);
            if (!text) continue;
            std::string value(reinterpret_cast<const char*>(text));
            for (char& c : value) if (c == '\t' || c == '\n' || c == '\r') c = ' ';
            std::cout << value;
        }
        std::cout << '\n';
    }
    sqlite3_finalize(stmt);
}

std::vector<std::pair<std::string, std::string>> read_batch(const std::string& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot read batch file");
    std::vector<std::pair<std::string, std::string>> queries;
    std::map<std::string, bool> names;
    std::string line;
    std::string name;
    std::string sql;
    while (std::getline(input, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.rfind("@query ", 0) == 0) {
            if (!name.empty()) throw std::runtime_error("nested query block");
            name = trim(line.substr(7));
            if (name.empty() || names.count(name)) throw std::runtime_error("invalid query name");
            names[name] = true;
            sql.clear();
        } else if (line == "@end") {
            if (name.empty() || trim(sql).empty()) throw std::runtime_error("invalid query block");
            queries.emplace_back(name, trim(sql));
            name.clear();
            sql.clear();
        } else {
            if (name.empty()) {
                if (!trim(line).empty()) throw std::runtime_error("content outside query block");
            } else {
                if (!sql.empty()) sql.push_back(' ');
                sql += trim(line);
            }
        }
    }
    if (!name.empty()) throw std::runtime_error("unterminated query block");
    if (queries.empty()) throw std::runtime_error("empty batch");
    return queries;
}
}

int main(int argc, char** argv) {
    try {
        if (argc != 3 || (std::string(argv[1]) != "--sql" && std::string(argv[1]) != "--batch-file")) {
            std::cerr << "usage: catalog-query (--sql <statement> | --batch-file <absolute-file>)\n";
            return 64;
        }
        const char* env = std::getenv("HARBOR_CATALOG_DB");
        const std::string db_path = env ? env : "/opt/harbor/operations.db";
        sqlite3* db = nullptr;
        if (sqlite3_open_v2(db_path.c_str(), &db, SQLITE_OPEN_READONLY, nullptr) != SQLITE_OK) {
            if (db) sqlite3_close(db);
            throw std::runtime_error("cannot open catalog");
        }
        try {
            if (std::string(argv[1]) == "--sql") {
                emit_statement(db, argv[2]);
            } else {
                for (const auto& [name, sql] : read_batch(argv[2])) {
                    std::cout << "@result " << name << '\n';
                    emit_statement(db, sql);
                    std::cout << "@end\n";
                }
            }
            sqlite3_close(db);
        } catch (...) {
            sqlite3_close(db);
            throw;
        }
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << ex.what() << '\n';
        return 65;
    }
}
