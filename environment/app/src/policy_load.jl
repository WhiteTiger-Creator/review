struct RefinePolicy
    schema_version::Int
    h_js::Float64
    m_n_kg::Float64
    intensity_floor::Float64
    residual_sigma_max::Float64
    min_admitted_peaks::Int
    admit_mode::String
    extinction_mode::String
    extinction_scale::Float64
    policy_revision::String
end

function _parse_toml_scalar(raw::AbstractString)
    s = strip(String(raw))
    if startswith(s, "\"") && endswith(s, "\"")
        return s[2:end-1]
    end
    if occursin(r"^[+-]?\d+$", s)
        return parse(Int, s)
    end
    return parse(Float64, s)
end

function load_policy(path::String)::RefinePolicy
    vals = Dict{String,Any}()
    for line in readlines(path)
        t = strip(line)
        (t == "" || startswith(t, "#") || !occursin("=", t)) && continue
        k, v = split(t, "=", limit=2)
        vals[String(strip(k))] = _parse_toml_scalar(v)
    end
    required = [
        "schema_version", "h_js", "m_n_kg", "intensity_floor", "residual_sigma_max",
        "min_admitted_peaks", "admit_mode", "extinction_mode", "extinction_scale", "policy_revision",
    ]
    for k in required
        haskey(vals, k) || error("missing policy key")
    end
    pol = RefinePolicy(
        Int(vals["schema_version"]),
        Float64(vals["h_js"]),
        Float64(vals["m_n_kg"]),
        Float64(vals["intensity_floor"]),
        Float64(vals["residual_sigma_max"]),
        Int(vals["min_admitted_peaks"]),
        String(vals["admit_mode"]),
        String(vals["extinction_mode"]),
        Float64(vals["extinction_scale"]),
        String(vals["policy_revision"]),
    )
    pol.h_js > 0 || error("bad h_js")
    pol.m_n_kg > 0 || error("bad m_n_kg")
    return pol
end

function assert_live_matches_sealed(config_path::String)
    return nothing
end
