local pipeline = require("pipeline")

local M = {}

function M.main(_)
    io.stderr:write("memscope pipeline is not implemented\n")
    return pipeline.run()
end

return M
