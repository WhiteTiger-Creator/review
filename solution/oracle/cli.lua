local pipeline = require("pipeline")

local M = {}

function M.main(arguments)
    if arguments[1] ~= "audit" or arguments[2] ~= "--config" or not arguments[3] then
        io.stderr:write("usage: memscope audit --config /app/config.json\n")
        return 2
    end

    local ok, message = xpcall(function()
        pipeline.run(arguments[3])
    end, debug.traceback)
    if not ok then
        io.stderr:write(tostring(message), "\n")
        return 1
    end
    return 0
end

return M
