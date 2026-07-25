# Reference / refined structure

## Reference input

Default path: `/app/data/sample/reference_structure.json`

Required keys:

```
a_A
b_A
c_A
alpha_deg
beta_deg
gamma_deg
crystal_system
```

Lengths (`*_A`) are positive finite Ångströms. Angles are finite degrees.

Supported `crystal_system` values (lowercase):

| system | free lengths | locked angles |
| --- | --- | --- |
| `cubic` | `a_A` only (`b_A` and `c_A` must equal `a_A`) | `alpha_deg=beta_deg=gamma_deg=90` |
| `tetragonal` | `a_A` (`b_A` must equal `a_A`), `c_A` | `alpha_deg=beta_deg=gamma_deg=90` |
| `orthorhombic` | `a_A`,`b_A`,`c_A` | `alpha_deg=beta_deg=gamma_deg=90` |
| `hexagonal` | `a_A` (`b_A` must equal `a_A`), `c_A` | `alpha_deg=beta_deg=90`, `gamma_deg=120` |

Angle equality uses absolute tolerance `1e-8` degrees. Length equality for locked axes uses absolute tolerance `1e-8` Å.

## Refined output

Default path: `/app/refined_structure.json`

Key order (exact):

```
a_A
b_A
c_A
alpha_deg
beta_deg
gamma_deg
crystal_system
```

Lengths formatted `%.10f`, angles `%.8f`. Trailing newline after `}`. Locked axes/angles must still be written explicitly with the refined values (not omitted).
