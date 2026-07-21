# heritage_at_risk

Flutter/Android client for **Heritage at Risk**: a threat map of UNESCO World
Heritage and archaeological sites across the MENA region. It reads only the
finished artefacts produced by the Python/DuckDB pipeline (`../artifacts/`) and
renders them with MapLibre Native.

See the [project README](../README.md) for the full description, the threat-score
methodology and the data sources, and `../PROJECT_CONTEXT.md` for notes on
approaches that were evaluated and dropped during development.

## Build

```sh
flutter pub get
flutter build apk --debug
```

Requires the Android toolchain (Flutter 3.44, JDK 21, Android SDK 36);
`maplibre_gl` needs Java 21 source compatibility.
