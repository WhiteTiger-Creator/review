# ELAST-X pricing pipeline

Kotlin/JVM pipeline that fits the ELAST-X demand model over a product-week panel and writes the
elasticity artifact. The modeling spec is in `docs/elast_x_memo.md`.

## Layout

- `src/main/kotlin/` the pipeline sources.
  - `Panel.kt` reads the panel CSV.
  - `Model.kt` prepares features, fits the model, derives elasticities and the holdout metric.
  - `Json.kt` serializes the result.
  - `Main.kt` argument handling.
- `data/panel.csv` a sample panel.
- `build.sh` compiles the sources to `engine.jar`.
- `run.sh` runs the jar.

## Build and run

    ./build.sh
    ./run.sh --panel data/panel.csv --out artifacts/elasticity.json

The current sources fit a generic pooled regression and do not follow the ELAST-X v2 methodology in the
memo. The fitted numbers differ from ELAST-X v2 accordingly.
