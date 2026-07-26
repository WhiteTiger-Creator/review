struct CrystalCell
    a_A::Float64
    b_A::Float64
    c_A::Float64
    alpha_deg::Float64
    beta_deg::Float64
    gamma_deg::Float64
    crystal_system::String
end

function load_structure(path::String)::CrystalCell
    txt = read(path, String)
    function num_field(name::String)
        m = match(Regex("\"" * name * "\"\\s*:\\s*([-+0-9.eE]+)"), txt)
        m === nothing && error("missing structure field")
        v = parse(Float64, m.captures[1])
        isfinite(v) || error("non-finite structure")
        return v
    end
    msys = match(r"\"crystal_system\"\s*:\s*\"([a-z]+)\"", txt)
    msys === nothing && error("missing crystal_system")
    cell = CrystalCell(
        num_field("a_A"), num_field("b_A"), num_field("c_A"),
        num_field("alpha_deg"), num_field("beta_deg"), num_field("gamma_deg"),
        msys.captures[1],
    )
    validate_reference_cell(cell)
    return cell
end

function nearly_eq(a::Float64, b::Float64, tol::Float64=1e-8)::Bool
    return abs(a - b) <= tol
end

function validate_reference_cell(cell::CrystalCell)
    cell.a_A > 0 && cell.b_A > 0 && cell.c_A > 0 || error("non-positive length")
    sys = cell.crystal_system
    if sys == "cubic"
        nearly_eq(cell.b_A, cell.a_A) && nearly_eq(cell.c_A, cell.a_A) || error("cubic length lock")
        nearly_eq(cell.alpha_deg, 90.0) && nearly_eq(cell.beta_deg, 90.0) && nearly_eq(cell.gamma_deg, 90.0) || error("cubic angle lock")
    elseif sys == "tetragonal"
        nearly_eq(cell.b_A, cell.a_A) || error("tetragonal length lock")
        nearly_eq(cell.alpha_deg, 90.0) && nearly_eq(cell.beta_deg, 90.0) && nearly_eq(cell.gamma_deg, 90.0) || error("tetragonal angle lock")
    elseif sys == "orthorhombic"
        nearly_eq(cell.alpha_deg, 90.0) && nearly_eq(cell.beta_deg, 90.0) && nearly_eq(cell.gamma_deg, 90.0) || error("orthorhombic angle lock")
    elseif sys == "hexagonal"
        nearly_eq(cell.b_A, cell.a_A) || error("hexagonal length lock")
        nearly_eq(cell.alpha_deg, 90.0) && nearly_eq(cell.beta_deg, 90.0) && nearly_eq(cell.gamma_deg, 120.0) || error("hexagonal angle lock")
    else
        error("unsupported crystal_system")
    end
end

function d_calc_A(cell::CrystalCell, h::Int, k::Int, l::Int)::Float64
    if cell.crystal_system == "hexagonal"
        q = (4.0 / 3.0) * (h * h + h * k + k * k) / (cell.a_A * cell.a_A) + (l * l) / (cell.c_A * cell.c_A)
    else
        q = (h / cell.a_A)^2 + (k / cell.b_A)^2 + (l / cell.c_A)^2
    end
    q <= 0 && error("non-positive Q")
    return 1.0 / sqrt(q)
end

function design_row(sys::String, h::Int, k::Int, l::Int)::Vector{Float64}
    if sys == "cubic"
        return Float64[h * h + k * k + l * l]
    elseif sys == "tetragonal"
        return Float64[h * h + k * k, l * l]
    elseif sys == "orthorhombic"
        return Float64[h * h, k * k, l * l]
    elseif sys == "hexagonal"
        return Float64[(4.0 / 3.0) * (h * h + h * k + k * k), Float64(l * l)]
    else
        error("unsupported crystal_system")
    end
end

function cell_from_x(sys::String, x::Vector{Float64})::CrystalCell
    if sys == "cubic"
        a = 1.0 / sqrt(x[1])
        return CrystalCell(a, a, a, 90.0, 90.0, 90.0, sys)
    elseif sys == "tetragonal"
        a = 1.0 / sqrt(x[1])
        c = 1.0 / sqrt(x[2])
        return CrystalCell(a, a, c, 90.0, 90.0, 90.0, sys)
    elseif sys == "orthorhombic"
        a = 1.0 / sqrt(x[1])
        b = 1.0 / sqrt(x[2])
        c = 1.0 / sqrt(x[3])
        return CrystalCell(a, b, c, 90.0, 90.0, 90.0, sys)
    elseif sys == "hexagonal"
        a = 1.0 / sqrt(x[1])
        c = 1.0 / sqrt(x[2])
        return CrystalCell(a, a, c, 90.0, 90.0, 120.0, sys)
    else
        error("unsupported crystal_system")
    end
end
