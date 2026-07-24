package audit

import (
    "bufio"
    "crypto/sha256"
    "encoding/hex"
    "os"
    "path/filepath"
    "sort"
    "strings"
)

type tmpEntry struct {
    Kind  string
    Path  string
    Mode  string
    User  string
    Group string
}

func parseKeyValueFile(path string) (map[string]string, error) {
    file, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer file.Close()
    values := map[string]string{}
    scanner := bufio.NewScanner(file)
    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())
        if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "[") {
            continue
        }
        key, value, ok := strings.Cut(line, "=")
        if !ok {
            continue
        }
        values[strings.TrimSpace(key)] = strings.TrimSpace(value)
    }
    if err := scanner.Err(); err != nil {
        return nil, err
    }
    return values, nil
}

func parseSimpleYAML(path string) (map[string]string, error) {
    file, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer file.Close()
    values := map[string]string{}
    scanner := bufio.NewScanner(file)
    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())
        if line == "" || strings.HasPrefix(line, "#") {
            continue
        }
        key, value, ok := strings.Cut(line, ":")
        if !ok {
            continue
        }
        values[strings.TrimSpace(key)] = strings.Trim(strings.TrimSpace(value), "\"")
    }
    if err := scanner.Err(); err != nil {
        return nil, err
    }
    return values, nil
}

func parseTmpfiles(path string) (map[string]tmpEntry, error) {
    file, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer file.Close()
    values := map[string]tmpEntry{}
    scanner := bufio.NewScanner(file)
    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())
        if line == "" || strings.HasPrefix(line, "#") {
            continue
        }
        fields := strings.Fields(line)
        if len(fields) < 5 {
            continue
        }
        entry := tmpEntry{Kind: fields[0], Path: fields[1], Mode: normalizeMode(fields[2]), User: fields[3], Group: fields[4]}
        values[entry.Path] = entry
    }
    if err := scanner.Err(); err != nil {
        return nil, err
    }
    return values, nil
}

func parseManifest(path string) (map[string]string, error) {
    return parseKeyValueFile(path)
}

func parseEnvironment(value string) map[string]string {
    out := map[string]string{}
    for _, field := range strings.Fields(value) {
        key, val, ok := strings.Cut(field, "=")
        if ok {
            out[strings.TrimSpace(key)] = strings.Trim(strings.TrimSpace(val), "\"")
        }
    }
    return out
}

func extractFlag(command, name string) string {
    prefix := name + "="
    fields := strings.Fields(command)
    for i, field := range fields {
        if strings.HasPrefix(field, prefix) {
            return strings.TrimPrefix(field, prefix)
        }
        if field == name && i+1 < len(fields) {
            return fields[i+1]
        }
    }
    return ""
}

func normalizeMode(value string) string {
    trimmed := strings.TrimSpace(value)
    if trimmed == "" || trimmed == "-" {
        return ""
    }
    trimmed = strings.TrimPrefix(trimmed, "0o")
    trimmed = strings.TrimPrefix(trimmed, "0O")
    for len(trimmed) < 4 {
        trimmed = "0" + trimmed
    }
    return trimmed
}

func sourceDigest(root string, rels []string) (string, error) {
    h := sha256.New()
    sorted := append([]string(nil), rels...)
    sort.Strings(sorted)
    for _, rel := range sorted {
        path := filepath.Join(root, filepath.FromSlash(rel))
        raw, err := os.ReadFile(path)
        if os.IsNotExist(err) {
            h.Write([]byte(rel + "=<absent>\n"))
            continue
        }
        if err != nil {
            return "", err
        }
        h.Write([]byte(rel + "\n"))
        h.Write(raw)
        if len(raw) == 0 || raw[len(raw)-1] != '\n' {
            h.Write([]byte("\n"))
        }
    }
    return hex.EncodeToString(h.Sum(nil)), nil
}
