local util = require("util")

local M = {}

local Store = {}
Store.__index = Store

local SCHEMA = {
    "PRAGMA journal_mode=DELETE;",
    "BEGIN;",
    "CREATE TABLE items(id TEXT PRIMARY KEY, modality TEXT NOT NULL, score REAL NOT NULL,"
        .. " lower REAL NOT NULL, upper REAL NOT NULL, substring_overlap REAL NOT NULL,"
        .. " semantic_overlap REAL NOT NULL, decision TEXT NOT NULL);",
    "CREATE TABLE probes(probe_index INTEGER PRIMARY KEY, item_id TEXT NOT NULL, kind TEXT NOT NULL,"
        .. " axis TEXT NOT NULL, value TEXT NOT NULL, seed INTEGER NOT NULL, correct INTEGER NOT NULL,"
        .. " logprob REAL NOT NULL, metadata_leak INTEGER NOT NULL, canary_recall INTEGER NOT NULL,"
        .. " completion TEXT NOT NULL);",
    "CREATE TABLE study(axis TEXT NOT NULL, value TEXT NOT NULL, mean_signal REAL NOT NULL,"
        .. " PRIMARY KEY(axis, value));",
}

local function text_literal(value)
    return "'" .. tostring(value):gsub("'", "''") .. "'"
end

local function label(value)
    if type(value) == "number" then
        return util.number_text(value)
    end
    return tostring(value)
end

function M.new()
    return setmetatable({items = {}, probes = {}, study = {}}, Store)
end

function Store:add_item(row)
    self.items[#self.items + 1] = string.format(
        "INSERT INTO items VALUES(%s,%s,%.17g,%.17g,%.17g,%.17g,%.17g,%s);",
        text_literal(row.id),
        text_literal(row.modality),
        row.score,
        row.lower,
        row.upper,
        row.substring_overlap,
        row.semantic_overlap,
        text_literal(row.decision)
    )
end

-- Records one issued probe and returns its probe_index. Rows are numbered in the
-- order they are added. A per item probe leaves axis and value empty; a study
-- probe carries the axis name and the axis value it was issued at.
function Store:add_probe(row)
    local index = #self.probes + 1
    self.probes[index] = string.format(
        "INSERT INTO probes VALUES(%d,%s,%s,%s,%s,%d,%d,%.17g,%d,%d,%s);",
        index,
        text_literal(row.item_id),
        text_literal(row.kind),
        text_literal(row.axis or ""),
        text_literal(row.value == nil and "" or label(row.value)),
        row.seed,
        row.correct,
        row.logprob,
        row.metadata_leak,
        row.canary_recall,
        text_literal(row.completion)
    )
    return index
end

function Store:add_study(row)
    self.study[#self.study + 1] = string.format(
        "INSERT INTO study VALUES(%s,%s,%.17g);",
        text_literal(row.axis),
        text_literal(label(row.value)),
        row.mean_signal
    )
end

function Store:probe_count()
    return #self.probes
end

-- Builds the database at the given path from the recorded rows.
function Store:write(path)
    local statements = {}
    for _, statement in ipairs(SCHEMA) do
        statements[#statements + 1] = statement
    end
    for _, group in ipairs({self.items, self.probes, self.study}) do
        for _, statement in ipairs(group) do
            statements[#statements + 1] = statement
        end
    end
    statements[#statements + 1] = "COMMIT;"
    local script = path .. ".sql"
    util.write_all(script, table.concat(statements, "\n") .. "\n")
    os.remove(path)
    local ok = os.execute("sqlite3 " .. util.shell_quote(path) .. " < " .. util.shell_quote(script))
    os.remove(script)
    assert(ok == true or ok == 0, "the database could not be built")
end

return M
