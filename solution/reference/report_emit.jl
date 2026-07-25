using SHA
import Printf: @sprintf

function fmt10f(x::Float64)::String
    y = ifelse(x == 0.0, 0.0, x)
    s = @sprintf("%.10f", y)
    return s == "-0.0000000000" ? "0.0000000000" : s
end

function fmt8f(x::Float64)::String
    y = ifelse(x == 0.0, 0.0, x)
    s = @sprintf("%.8f", y)
    return s == "-0.00000000" ? "0.00000000" : s
end

function atomic_write(path::String, data::String)
    dir = dirname(path)
    dir != "" && mkpath(dir)
    tmp = path * ".tmp"
    open(tmp, "w") do io
        write(io, data)
    end
    mv(tmp, path; force=true)
end

function refine_digest(states::Vector{PeakState}, cell::CrystalCell, chi2::Float64, rms::Float64, pol::RefinePolicy)::String
    lines = String["rev:" * pol.policy_revision]
    for s in states
        rej = s.rejected ? "1" : "0"
        push!(lines, s.row.peak_id * ":" * fmt10f(s.d_obs_A) * ":" * fmt10f(s.d_calc_A) * ":" * fmt10f(s.resid_sigma) * ":" * rej)
    end
    push!(lines, "a:" * fmt10f(cell.a_A) * ":b:" * fmt10f(cell.b_A) * ":c:" * fmt10f(cell.c_A) * ":chi2:" * fmt10f(chi2) * ":rms:" * fmt10f(rms))
    blob = join(lines, "\n")
    return bytes2hex(sha256(blob))
end

function write_refined_json(path::String, cell::CrystalCell)
    body =
        "{\n" *
        "  \"a_A\": " * fmt10f(cell.a_A) * ",\n" *
        "  \"b_A\": " * fmt10f(cell.b_A) * ",\n" *
        "  \"c_A\": " * fmt10f(cell.c_A) * ",\n" *
        "  \"alpha_deg\": " * fmt8f(cell.alpha_deg) * ",\n" *
        "  \"beta_deg\": " * fmt8f(cell.beta_deg) * ",\n" *
        "  \"gamma_deg\": " * fmt8f(cell.gamma_deg) * ",\n" *
        "  \"crystal_system\": \"" * cell.crystal_system * "\"\n" *
        "}\n"
    atomic_write(path, body)
end

function write_report_json(path::String, pol::RefinePolicy, cell::CrystalCell, states::Vector{PeakState}, chi2::Float64, rms::Float64)
    rejected_ids = [s.row.peak_id for s in states if s.rejected]
    digest = refine_digest(states, cell, chi2, rms, pol)
    io = IOBuffer()
    print(io, "{\n")
    print(io, "  \"schema_version\": ", pol.schema_version, ",\n")
    print(io, "  \"policy_revision\": \"", pol.policy_revision, "\",\n")
    print(io, "  \"crystal_system\": \"", cell.crystal_system, "\",\n")
    print(io, "  \"peak_count\": ", length(states), ",\n")
    print(io, "  \"admitted_count\": ", count(s -> !s.rejected, states), ",\n")
    print(io, "  \"rejected_count\": ", length(rejected_ids), ",\n")
    print(io, "  \"chi2\": ", chi2, ",\n")
    print(io, "  \"rms_resid_A\": ", rms, ",\n")
    print(io, "  \"a_A\": ", fmt10f(cell.a_A), ",\n")
    print(io, "  \"b_A\": ", fmt10f(cell.b_A), ",\n")
    print(io, "  \"c_A\": ", fmt10f(cell.c_A), ",\n")
    print(io, "  \"alpha_deg\": ", fmt8f(cell.alpha_deg), ",\n")
    print(io, "  \"beta_deg\": ", fmt8f(cell.beta_deg), ",\n")
    print(io, "  \"gamma_deg\": ", fmt8f(cell.gamma_deg), ",\n")
    print(io, "  \"rejected_ids\": [")
    for (i, pid) in enumerate(rejected_ids)
        i > 1 && print(io, ", ")
        print(io, "\"", pid, "\"")
    end
    print(io, "],\n")
    print(io, "  \"residuals\": [\n")
    for (i, s) in enumerate(states)
        print(io, "    {\n")
        print(io, "      \"peak_id\": \"", s.row.peak_id, "\",\n")
        print(io, "      \"h\": ", s.row.h, ",\n")
        print(io, "      \"k\": ", s.row.k, ",\n")
        print(io, "      \"l\": ", s.row.l, ",\n")
        print(io, "      \"d_obs_A\": ", fmt10f(s.d_obs_A), ",\n")
        print(io, "      \"d_calc_A\": ", fmt10f(s.d_calc_A), ",\n")
        print(io, "      \"resid_sigma\": ", fmt10f(s.resid_sigma), ",\n")
        print(io, "      \"rejected\": ", s.rejected ? "true" : "false", "\n")
        print(io, "    }")
        i < length(states) && print(io, ",")
        print(io, "\n")
    end
    print(io, "  ],\n")
    print(io, "  \"refine_digest\": \"", digest, "\"\n")
    print(io, "}\n")
    atomic_write(path, String(take!(io)))
end
