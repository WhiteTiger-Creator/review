include("/app/src/peak_load.jl")
include("/app/src/policy_load.jl")
include("/app/src/instrument_geom.jl")
include("/app/src/lattice_metric.jl")
include("/app/src/refine_ls.jl")
include("/app/src/report_emit.jl")

function parse_args(args::Vector{String})
    defaults = Dict(
        "peaks" => "/app/data/sample/peaks.csv",
        "instrument" => "/app/data/sample/instrument.json",
        "structure" => "/app/data/sample/reference_structure.json",
        "config" => "/app/config/refine_policy.toml",
        "refined" => "/app/refined_structure.json",
        "report" => "/app/refinement_report.json",
    )
    seen = Dict{String,Bool}()
    i = 1
    while i <= length(args)
        a = args[i]
        startswith(a, "--") || error("bad flag")
        key = a[3:end]
        haskey(defaults, key) || error("unknown flag")
        haskey(seen, key) && error("dup flag")
        i == length(args) && error("missing value")
        defaults[key] = args[i + 1]
        seen[key] = true
        i += 2
    end
    paths = [
        defaults["peaks"], defaults["instrument"], defaults["structure"],
        defaults["config"], defaults["refined"], defaults["report"],
    ]
    length(unique(paths)) == 6 || error("path collision")
    return defaults
end

function main()
    try
        opts = parse_args(ARGS)
        assert_live_matches_sealed(opts["config"])
        policy = load_policy(opts["config"])
        peaks = load_peaks_csv(opts["peaks"])
        geom = load_instrument(opts["instrument"])
        ref = load_structure(opts["structure"])
        cell, states, chi2, rms = refine_pack(peaks, geom, ref, policy)
        write_refined_json(opts["refined"], cell)
        write_report_json(opts["report"], policy, cell, states, chi2, rms)
        rejected = count(s -> s.rejected, states)
        exit(rejected == 0 ? 0 : 1)
    catch e
        println(stderr, sprint(showerror, e))
        exit(2)
    end
end

main()
