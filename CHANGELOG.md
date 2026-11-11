# Changelog

## 1.7.1

- `generate_music()` now returns the run's generation metadata in `result["metadata"]`. Until
  now it was always `{}`: the SDK looked for it under `analysis`, where the API doesn't store it.
- When you leave out the lyrics for text to music (and `instrumental` is False), Audial writes
  lyrics from your prompt and sings them. They come back in
  `result["metadata"]["written_lyrics"]`, and `generate_music()` prints them. Before, the
  vocals had no words. Pass `instrumental=True` for no vocals.
- `result["metadata"]["audio_seconds"]` has the length of each file.
- Docs: `audio_duration` goes up to 360 s (not 600); longer values are capped. Without it the
  length follows the lyrics, and a cover follows its reference.

## 1.7.0

- `audial.tags()` returns the tags exactly as the Audial website shows them: `genre` (display
  names, with no `---`: use them as they are), `song_tags`, `description` and `warnings`.
- `song_tags` has five parts: `full` (the mix, with `artist_tags`), `drums`, `bass`, `melody` and
  `vocals`. A part whose stem is silent has `"silent": True` and empty lists. Tracks analysed
  before this release have the first three parts only.
- `description` is a short written description of the track, `""` when there is none.
- `tags_version`, `source` and `extra_tags` are no longer returned.
- `audial tags` prints the description first, then the genres as they are, then each part.

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
- `segment()` keeps its 1.5 parameters and their order. `components` and `analysis_type` are
  accepted and ignored (deprecated). The new `edm`, `expand_beats` and `max_wait` are keyword-only.
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
