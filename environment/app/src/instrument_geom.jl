struct InstrumentGeom
    L1_m::Float64
    L2_m::Float64
    two_theta_deg::Float64
    pulse_offset_us::Float64
end

function load_instrument(path::String)::InstrumentGeom
    txt = read(path, String)
    function num_field(name::String)
        m = match(Regex("\"" * name * "\"\\s*:\\s*([-+0-9.eE]+)"), txt)
        m === nothing && error("missing instrument field")
        v = parse(Float64, m.captures[1])
        isfinite(v) || error("non-finite instrument")
        return v
    end
    g = InstrumentGeom(num_field("L1_m"), num_field("L2_m"), num_field("two_theta_deg"), num_field("pulse_offset_us"))
    g.L1_m > 0 || error("bad L1")
    g.L2_m > 0 || error("bad L2")
    (g.two_theta_deg > 0 && g.two_theta_deg < 180) || error("bad two_theta")
    return g
end

function tof_to_d(tof_us::Float64, sigma_tof::Float64, geom::InstrumentGeom, pol::RefinePolicy)
    t_s = tof_us * 1e-6
    sigma_t_s = sigma_tof * 1e-6
    L_m = geom.L1_m
    theta = deg2rad(geom.two_theta_deg / 2.0)
    s = sin(theta)
    s == 0 && error("zero sin theta")
    d_m = pol.h_js * t_s / (2.0 * L_m * s * pol.m_n_kg)
    sigma_d_m = pol.h_js * sigma_t_s / (2.0 * L_m * s * pol.m_n_kg)
    return d_m * 1e10, sigma_d_m * 1e10
end
