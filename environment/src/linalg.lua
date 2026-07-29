local M = {}

-- Solves a dense square system by Gaussian elimination with partial pivoting.
-- The matrix is a list of rows and the right hand side a flat list of the same
-- length. Raises when the system is singular.
function M.solve(matrix, rhs)
    local size = #rhs
    local work = {}
    for row = 1, size do
        work[row] = {}
        for column = 1, size do
            work[row][column] = matrix[row][column]
        end
        work[row][size + 1] = rhs[row]
    end

    for column = 1, size do
        local pivot = column
        for row = column + 1, size do
            if math.abs(work[row][column]) > math.abs(work[pivot][column]) then
                pivot = row
            end
        end
        work[column], work[pivot] = work[pivot], work[column]
        local head = work[column][column]
        assert(math.abs(head) > 1e-14, "the system is singular")
        for row = 1, size do
            if row ~= column then
                local factor = work[row][column] / head
                for index = column, size + 1 do
                    work[row][index] = work[row][index] - factor * work[column][index]
                end
            end
        end
    end

    local solution = {}
    for row = 1, size do
        solution[row] = work[row][size + 1] / work[row][row]
    end
    return solution
end

return M
