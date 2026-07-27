# Tidefront water-depth mechanics

Tidefront boards reference station IDs from the station bundle. The bundle, constituent catalog, and leap table use the schemas documented in `station-bundle.md`, `catalog-format.md`, and `leap-table.md`. The game engine evaluates one harmonic water-level sample per referenced station and turn before resolving movement.

Station, region, and global overrides are applied independently for datum, scale, and phase offset. Explicit zero values remain meaningful. Required constituents must exist, optional missing constituents are ignored, nodal factors use cubic Hermite interpolation, and phase interpolation follows the shortest wrapped arc. Samples outside catalog coverage are invalid. Turn timestamps advance on the TAI timeline so a declared UTC leap second is represented as its own turn.
