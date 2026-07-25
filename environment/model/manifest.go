
package model

import (
    "encoding/json"
    "os"

    "github.com/local/etaengine/types"
)

type Manifest struct {
    DeclaredScale float32 `json:"declared_scale"`
    Fields        int     `json:"fields"`
    SparseSlots   int     `json:"sparse_slots"`
    WeightsPath   string  `json:"weights_path"`
}

func LoadManifest(path string) (*Manifest, error) {
    b, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }
    var m Manifest
    if err := json.Unmarshal(b, &m); err != nil {
        return nil, err
    }
    return &m, nil
}

func CapsFromManifest(m *Manifest) types.FieldCaps {
    return types.FieldCaps{
        Fields:        m.Fields,
        SparseSlots:   m.SparseSlots,
        DeclaredScale: m.DeclaredScale,
    }
}
