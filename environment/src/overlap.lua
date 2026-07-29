local M = {}

local function words(text)
    local result = {}
    for word in text:lower():gmatch("[%w]+") do
        result[#result + 1] = word
    end
    return result
end

local function longest_run(left, right)
    local best = 0
    for left_index = 1, #left do
        for right_index = 1, #right do
            local length = 0
            while left_index + length <= #left
                and right_index + length <= #right
                and left[left_index + length] == right[right_index + length]
            do
                length = length + 1
            end
            if length > best then
                best = length
            end
        end
    end
    return best
end

-- Longest run of consecutive words the prompt shares with any corpus passage,
-- as a fraction of the prompt length. One means the whole prompt is present verbatim.
function M.substring(prompt, corpus_rows)
    local prompt_words = words(prompt)
    if #prompt_words == 0 then
        return 0
    end
    local best = 0
    for _, row in ipairs(corpus_rows) do
        local run = longest_run(prompt_words, words(row.text))
        if run > best then
            best = run
        end
    end
    return best / #prompt_words
end

local function cosine(left, right)
    assert(#left == #right and #left > 0, "embedding dimensions differ")
    local dot = 0
    local left_norm = 0
    local right_norm = 0
    for index = 1, #left do
        dot = dot + left[index] * right[index]
        left_norm = left_norm + left[index] * left[index]
        right_norm = right_norm + right[index] * right[index]
    end
    if left_norm == 0 or right_norm == 0 then
        return 0
    end
    return dot / math.sqrt(left_norm * right_norm)
end

-- Largest cosine similarity between the item embedding and any corpus embedding record.
function M.semantic(embedding, embedding_rows)
    assert(#embedding_rows > 0, "no corpus embeddings were supplied")
    local best = -1
    for _, row in ipairs(embedding_rows) do
        local value = cosine(embedding, row.embedding)
        if value > best then
            best = value
        end
    end
    return best
end

return M
