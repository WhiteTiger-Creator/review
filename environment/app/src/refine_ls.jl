mutable struct PeakState
    row::PeakRow
    d_obs_A::Float64
    sigma_d_A::Float64
    weight::Float64
    primary_reject::Bool
    residual_reject::Bool
    rejected::Bool
    d_calc_A::Float64
    resid_sigma::Float64
end

function _primary_reject(row::PeakRow, pol::RefinePolicy)::Bool
    return row.intensity < pol.intensity_floor
end

function _base_weight(d_obs::Float64, sigma_d::Float64, row::PeakRow, pol::RefinePolicy)::Float64
    return 1.0 / max(sigma_d, 1e-12)
end

function _solve_normal(A::Matrix{Float64}, w::Vector{Float64}, q::Vector{Float64})::Vector{Float64}
    n = size(A, 2)
    AtWA = zeros(Float64, n, n)
    AtWq = zeros(Float64, n)
    for i in 1:size(A, 1)
        wi = w[i]
        for c in 1:n
            AtWq[c] += wi * A[i, c] * q[i]
            for r in 1:n
                AtWA[r, c] += wi * A[i, r] * A[i, c]
            end
        end
    end
    M = [AtWA AtWq]
    for col in 1:n
        pivot = col
        best = abs(M[col, col])
        for r in (col + 1):n
            if abs(M[r, col]) > best
                best = abs(M[r, col])
                pivot = r
            end
        end
        best == 0 && error("singular normal")
        if pivot != col
            tmp = M[col, :]
            M[col, :] = M[pivot, :]
            M[pivot, :] = tmp
        end
        piv = M[col, col]
        for c in col:(n + 1)
            M[col, c] /= piv
        end
        for r in 1:n
            r == col && continue
            f = M[r, col]
            for c in col:(n + 1)
                M[r, c] -= f * M[col, c]
            end
        end
    end
    return M[:, n + 1]
end

function _fit_cell(states::Vector{PeakState}, sys::String, pol::RefinePolicy)::CrystalCell
    admitted = [s for s in states if !s.rejected]
    length(admitted) < pol.min_admitted_peaks && error("too few admitted")
    nrows = length(admitted)
    ncols = length(design_row(sys, admitted[1].row.h, admitted[1].row.k, admitted[1].row.l))
    A = zeros(Float64, nrows, ncols)
    w = zeros(Float64, nrows)
    q = zeros(Float64, nrows)
    for (i, s) in enumerate(admitted)
        A[i, :] = design_row(sys, s.row.h, s.row.k, s.row.l)
        w[i] = s.weight
        q[i] = 1.0 / (s.d_obs_A * s.d_obs_A)
    end
    x = _solve_normal(A, w, q)
    any(xi -> !(isfinite(xi) && xi > 0), x) && error("bad metric")
    return cell_from_x(sys, x)
end

function _apply_residuals!(states::Vector{PeakState}, cell::CrystalCell)
    for s in states
        s.d_calc_A = d_calc_A(cell, s.row.h, s.row.k, s.row.l)
        s.resid_sigma = (s.d_obs_A - s.d_calc_A) / s.sigma_d_A
    end
end

function refine_pack(peaks::Vector{PeakRow}, geom::InstrumentGeom, ref::CrystalCell, pol::RefinePolicy)
    states = PeakState[]
    for row in peaks
        d_obs, sigma_d = tof_to_d(row.tof_us, row.sigma_tof, geom, pol)
        primary = _primary_reject(row, pol)
        w = primary ? 0.0 : _base_weight(d_obs, sigma_d, row, pol)
        push!(states, PeakState(row, d_obs, sigma_d, w, primary, false, primary, 0.0, 0.0))
    end
    cell = _fit_cell(states, ref.crystal_system, pol)
    _apply_residuals!(states, cell)
    admitted = [s for s in states if !s.rejected]
    isempty(admitted) && error("zero admitted final")
    chi2 = sum(s.resid_sigma^2 for s in admitted)
    rms = sqrt(sum((s.d_obs_A - s.d_calc_A)^2 for s in admitted) / length(admitted))
    sort!(states, by = s -> s.row.peak_id)
    return cell, states, chi2, rms
end
