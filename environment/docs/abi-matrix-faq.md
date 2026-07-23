# ABI matrix FAQ

The matrix treats ABI family as an output identity, not just a compiler name. A
host compiler may be used for local simulation, but the descriptor ABI still
controls the public object identity and exported consumer defines.

The `identity` and `mix` object units are cached separately because they do not
depend on the same source file. Header, descriptor, toolchain, interface
fragment, and build-driver changes affect both units; a change to one unit's C
source affects only that unit. The interface fragment is part of the ABI capsule
because downstream CMake consumers receive compile definitions through generated
package metadata rather than through the archive alone.
