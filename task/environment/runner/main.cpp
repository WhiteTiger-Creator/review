#include "emit_pipeline.h"
#include <iostream>

int main(int argc, char **argv) {
    try {
        return forge_run_emit(argc, argv);
    } catch (const std::exception &e) {
        std::cerr << "forge_emit: " << e.what() << '\n';
        return 1;
    }
}
