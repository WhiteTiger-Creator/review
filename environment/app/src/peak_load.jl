struct PeakRow
    peak_id::String
    h::Int
    k::Int
    l::Int
    tof_us::Float64
    intensity::Float64
    sigma_tof::Float64
    extinct_flag::Int
end

const PEAK_HEADER = ["peak_id", "h", "k", "l", "tof_us", "intensity", "sigma_tof", "extinct_flag"]

function load_peaks_csv(path::String)::Vector{PeakRow}
    lines = readlines(path)
    isempty(lines) && error("empty peaks")
    hdr = split(strip(lines[1]), ",")
    hdr == PEAK_HEADER || error("bad peaks header")
    length(lines) < 2 && error("empty peaks")
    seen = Dict{String,Bool}()
    out = PeakRow[]
    for line in lines[2:end]
        strip(line) == "" && continue
        cols = split(line, ",")
        length(cols) == 8 || error("bad peaks width")
        pid = cols[1]
        pid == "" && error("blank peak_id")
        haskey(seen, pid) && error("duplicate peak_id")
        seen[pid] = true
        h = parse(Int, cols[2])
        k = parse(Int, cols[3])
        l = parse(Int, cols[4])
        abs(h) + abs(k) + abs(l) == 0 && error("zero miller")
        tof = parse(Float64, cols[5])
        inten = parse(Float64, cols[6])
        sig = parse(Float64, cols[7])
        ex = parse(Int, cols[8])
        (isfinite(tof) && isfinite(inten) && isfinite(sig)) || error("non-finite")
        inten < 0 && error("negative intensity")
        sig <= 0 && error("bad sigma")
        (ex == 0 || ex == 1) || error("bad extinct_flag")
        push!(out, PeakRow(pid, h, k, l, tof, inten, sig, ex))
    end
    isempty(out) && error("empty peaks")
    return out
end
