# Changelog

## 2.0.0

Analysis results are in analysis format 5, the same object the API serves and the website's JSON
button saves: every fact appears once, every section carries its own numbers, nothing only
means something inside Audial, and units are stated (times in seconds, `energy` and
`danceability` 0 to 1, `loudness_lufs` in LUFS). Older analyses are served in format 5 too.
This release breaks 1.x scripts that read analysis results; how to update one is below.

- `segment()` returns `{analysis_id, analysis, execution, files, warnings?}`. `analysis` is the
  format 5 merged view: `format_version` (5), `duration`, `bpm`, `tempo_mode`,
  `time_signature`, `key`, `camelot`, `structure`, `bar1`, `grid`, `lead_in`, `sections`
  (`label`, `start`, `end`, `start_bar`, `bars`, `fills`, and once audio features have run
  `energy`, `danceability`, `loudness_lufs`), and once their add-on has run `features`, `tags`,
  `description` and `lyrics`. The `audio_segmentation` and `segmentation` keys are gone.
  `analysis.json` holds the format 5 object itself, with no wrapper.
- `expand_beats` is now False by default, and no `FutureWarning` is shown. With
  `expand_beats=True`, `analysis` also has `beat_times` and `bar_times`.
- `audio_features()` returns `{key, camelot, features, sections, warnings}`: the analysis's key,
  the `features` block (`energy`, `danceability`, `loudness_lufs`, `mode`, `mode_confidence`,
  `tatum`) and each section's `label`, `start`, `end`, `energy`, `danceability` and
  `loudness_lufs`.
- `tags()` returns `{genres, instruments, moods, stems, description, warnings}`. A part of
  `stems` (`drums`, `bass`, `melody`, `vocals`) is `{instruments, moods}`, or `{"silent": True}`
  when that part is silent. Artist tags are gone.
- `lyrics()` returns `{vocal_start, lines, warnings}`. `vocal_start` replaces
  `first_vocal_beat_time`. `lyrics` (the text: the words of `lines` joined), `is_instrumental`
  (no vocals: `vocal_start` is None and `lines` is empty), `segments` and `section_lyrics` are
  gone.
- The three add-ons read their values from the merged view, so they match `segment()` and the
  website; `warnings` comes from the run.
- `audial.grid.beats_of`, `beat_times`, `bar_times` and `expand` take a format 5 analysis (or the
  whole `segment()` result) as well as a `grid`, a format 4 file (with or without its wrapper)
  or a format 2/3 file. Beats per bar come from `time_signature` (4 when there is none); a
  format 4 grid's `beats_per_bar` is still read. New `audial.grid.beats_per_bar()`.
- `audial segment`, `audial features`, `audial tags` and `audial lyrics` print the new fields
  (the key, loudness per section, genres and each part's tags, when the vocals start).

### Updating a 1.x script

| 1.x | 2.0 |
|---|---|
| `result["audio_segmentation"]`, `result["segmentation"]` | `result["analysis"]` |
| `["mode"]` (dance or song) | `["structure"]` |
| `["song_analysis"]["key"]` | `["key"]` (and `["camelot"]`) |
| `["song_analysis"]["energy"]`, `danceability`, `mode`, `mode_confidence`, `tatum` | `["features"][...]` |
| `["song_analysis"]["loudness"]` | `["features"]["loudness_lufs"]` |
| `["segment_analysis"][i]["energy"]` | `["sections"][i]["energy"]` (`loudness` is `loudness_lufs`) |
| `["song_analysis"]["genre"]`, `song_tags.full` | `["tags"]["genres"]`, `["tags"]["instruments"]`, `["tags"]["moods"]` |
| `song_tags.<part>` | `["tags"]["stems"][part]` (`{"silent": True}` when silent) |
| `["song_analysis"]["description"]` | `["description"]` |
| `["song_analysis"]["lyrics_lines"]` | `["lyrics"]["lines"]` |
| `["first_vocal_beat_time"]` | `["lyrics"]["vocal_start"]` |
| `["song_start"]` | `["bar1"]` (`lead_in` covers the time before it) |
| `phrases`, `mood`, `filtered_segments`, `segment_classifications`, `bar_analysis`, `timebase`, `mode_source`, artist tags | gone |
| `grid["beats_per_bar"]` | `audial.grid.beats_per_bar(analysis)` (from `time_signature`) |
| `beat_times`, `bar_times` (added by default) | `audial.grid.beats_of(result)`, or `expand_beats=True` |
| `audio_features()["song"]` | `audio_features()["features"]`, with `["key"]` beside it |
| `tags()["genre"]`, `tags()["song_tags"]` | `tags()["genres"]`, `["instruments"]`, `["moods"]`, `["stems"]` |
| `lyrics()["first_vocal_beat_time"]`, `["is_instrumental"]`, `["lyrics"]` | `lyrics()["vocal_start"]`, `not lyrics()["lines"]`, the words of `lines` joined |

## 1.8.0

- New `AudialLimitReached` (a subclass of `AudialAPIError`), raised when the account has used
  all its API calls for the month (HTTP 402, code `API_LIMIT_REACHED`). It has `limit`, `used`,
  `resets_at` (a UTC `datetime`) and `upgrade_url`, and its message is one line, e.g.
  "Monthly API limit reached (100/100). Resets 2026-12-23. More calls: https://audialmusic.ai/product/pricing".
  It is final until the reset, so the SDK makes one request and does not retry. The free
  allowance running out is still `SubscriptionRequiredError`.
- A 429 (5 calls a minute per account) now waits at least as long as the `Retry-After` header
  says before the SDK retries; without the header the old backoff applies.
- New `audial.usage()` returns the `api` block of `/functions/allowance`: `plan`,
  `monthlyLimit`, `used`, `remaining`, `topupRemaining`, `resetsAt` (ms). `None` if absent.

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
