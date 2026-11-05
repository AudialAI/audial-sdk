# Changelog

## 1.6.0

- Analysis is faster and needs only the mix.
- Features, tags and lyrics are separate calls on an analysis.
- Lyrics now come with word timings.
- Analysis files describe beats with a tempo map (`grid`); the SDK still returns `beat_times`
  and `bar_times`.
- Energy and danceability were rebuilt and now differ between tracks and sections.
- Loudness now follows the broadcast standard over both channels and reads 3–6 LU higher than
  before.

### In the SDK

- `audial.segment(file)` is one call that answers in about half a minute and returns an
  `analysis_id`. Without `features` it no longer makes features, tags or lyrics: add them with
  `audial.audio_features(analysis_id)`, `audial.tags(analysis_id)` and
  `audial.lyrics(analysis_id)`, or pass `features=[...]` as before (the `segmentation` pipeline,
  which takes longer).
- `segment()` returns the analysis with every add-on so far (`audio_segmentation`, also under its
  1.5 name `segmentation`) and saves it as `analysis.json`.
- New `segment()` parameters: `edm` (dance or song section names) and `expand_beats`.
  `expand_beats=True`, the default in 1.6, adds `beat_times` and `bar_times` computed from `grid`.
  2.0 makes it opt-in, and a one-time `FutureWarning` says so.
- `segment()`'s second positional parameter is now `genre`. `components` and `analysis_type` are
  accepted by name and ignored (deprecated).
- Tags, lyrics and sample packs read the analysis's stems, which are made automatically. While
  they are being made the API answers `409 STEMS_NOT_READY`; the add-on functions keep trying for
  up to `wait_s` seconds (default 600).
- `audial.generate_samples(analysis_id=...)` makes a sample pack from an analysis's stems and
  sections. `file_path` is optional when `analysis_id` is given.
- `audial.grid`: `expand()`, `beat_times()`, `bar_times()` and `beats_of()` for the tempo map.
- `AudialAPIError.code` holds the API's error code (`STEMS_NOT_READY`, `ADDON_UNAVAILABLE`, …).
- CLI: `audial features`, `audial tags` and `audial lyrics` take an analysis id or a file (a file
  is analysed first). `audial segment` runs the fast analysis unless `--features` is given, and
  gains `--edm`/`--no-edm` and `--json`. `audial generate-samples --analysis-id`. `python -m
  audial` runs the CLI.
- Pipelines report the API's step names: `segmentation` then `add-ons`, and `prepare` then
  `sample-pack`.
