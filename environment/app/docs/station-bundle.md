# Station bundle format

A station bundle is strict JSON. Duplicate object keys, unknown fields, trailing JSON values, and wrong JSON types are invalid.

The top-level object has `schema_version` equal to 1, optional `global`, optional `regions`, and a nonempty `stations` array. `regions` maps nonempty region names to override objects. Override objects may contain `datum_m`, `scale`, and `phase_offset_deg`, each a finite JSON number. Omitted fields inherit according to the forecast contract; zero is a real override.

Each station contains `id`, optional `region`, `latitude_deg`, `longitude_deg`, optional `overrides`, and a nonempty `constituents` array. IDs are nonempty and unique. Latitude is within `[-90, 90]`; longitude is within `[-180, 180]`. A nonempty region must exist in the top-level region map.

Each constituent use contains exactly `name`, `amplitude_m`, `phase_deg`, and `required`. The name is nonempty and unique within the station, amplitude is finite and nonnegative, phase is finite, and required is a JSON boolean.
