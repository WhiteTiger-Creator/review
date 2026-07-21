# Compile notes

Configure and build from `/app`:

```
cmake -S /app/environment -B /app/build -G Ninja
ninja -C /app/build
```

The runtime binary is `/app/build/forge_emit`. Typical invocation:

```
/app/build/forge_emit /app/environment/fixtures/lane.json /app/output/forge_emit.json
```

The bundled manifest lists three units with record paths relative to the manifest directory.
