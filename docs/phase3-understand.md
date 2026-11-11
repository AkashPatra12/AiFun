# Phase 3 — Engine: Understand MVP

Scope: real Whisper transcription, scene + transcript highlight scoring,
and photo aesthetic scoring (`docs/README.md`'s features #2 photo scoring →
actually #4, #3 smart clip selection, #6 auto captions' transcription half).
**Deliberately not wired into the live upload → process pipeline** — that
pipeline still runs Phase 2's fixture (`aifun.editing.highlights`); swapping
it for this module's real output is Phase 4, a separate step (see
`docs/progress.md`). This phase is standalone by design, same as
`docs/README.md`'s original team-split intent: testable via CLI/pytest with
no API, DB, or queue involved.

---

## 1. What's here

| Module | Does |
|---|---|
| `aifun/transcribe/__init__.py` | Local Whisper transcription → list of `{start, end, text}` segments |
| `aifun/analysis/scenes.py` | Shot-boundary detection (PySceneDetect `ContentDetector`) |
| `aifun/analysis/motion.py` | Per-scene motion score (frame-diff) + face presence (Haar cascade) |
| `aifun/analysis/__init__.py` | `find_highlights()` — combines the above into a scored, contract-shaped highlight list |
| `aifun/analysis/photo_score.py` | Photo scoring: sharpness, exposure, face presence → one `score` |

CLI entry points (`aifun/cli.py`), the standalone surface this phase is
tested through:

```bash
aifun transcribe <video>                                   # prints segments as JSON
aifun analyze <video> --output-path highlights.json         # writes a highlights.json fixture
aifun score-photo <image>                                   # prints {sharpness, exposure, hasFace, score}
```

## 2. Highlight scoring (MVP heuristic, not ML/LLM)

`find_highlights()` scores each detected scene as:

```
score = 0.4 * motion + 0.3 * (1.0 if face_detected else 0.0) + 0.3 * speech_density
```

- **motion** — mean frame-to-frame pixel difference across a few sampled
  frames, normalized (`aifun.analysis.motion.score_motion`)
- **face_detected** — any sampled frame has a detected face (Haar cascade)
- **speech_density** — words-per-second of Whisper transcript overlapping
  the scene, normalized (2.5 words/sec ≈ ceiling)

Scenes shorter than `min(target_duration_seconds[0], 3.0)` (from
`config/settings.yaml`) are dropped rather than merged into neighbors —
merging adjacent short scenes into a properly-paced clip is a real
refinement, deferred past this MVP. If every scene gets dropped, one
fallback highlight covering the available duration is returned instead of
an empty list. Results are capped at `max_clips_per_video` and sorted by
score, descending.

This is a heuristic, not a trained model or LLM call — `config/settings.yaml`
lists `analysis.llm_model: claude-sonnet-5`, but there's no `ANTHROPIC_API_KEY`
configured (`engine/.env.example` leaves it blank) and no LLM-based scoring
implemented here. Revisit once there's a reason to spend real API cost per
reel (this project's stated goal is $0/reel — see `docs/README.md` §4).

## 3. Decisions and gotchas

- **Whisper model: `tiny`, not `config/settings.yaml`'s `whisper-large-v3`.**
  The tech stack section of `docs/README.md` explicitly calls for a
  "tiny/base model, CPU-friendly" for the $0/local-compute goal;
  `large-v3` is a multi-GB model that contradicts that. `model_size` is a
  parameter on `transcribe_video()`/the CLI, so bumping it later is a
  one-line change — `config/settings.yaml`'s value hasn't been corrected to
  match, since nothing reads that particular key yet.
- **`opencv-python` pinned to `>=4.8,<5`.** OpenCV 5.0 (the unpinned
  default at the time this was written) removed `cv2.CascadeClassifier` and
  the bundled Haar cascade XML files entirely, in favor of a DNN-based
  `FaceDetectorYN` that needs an external ONNX model file. Pinning to 4.x
  keeps face detection self-contained with no extra model download —
  revisit if/when the project moves to the DNN detector deliberately.
- **Whisper's model download needs a real CA bundle.** Some local Python
  installs (notably python.org's macOS builds) don't wire the OS trust
  store into Python's default SSL context, so whisper's plain-`urllib`
  download of model weights fails with `CERTIFICATE_VERIFY_FAILED` even
  though the network is fine. `aifun/transcribe/__init__.py` works around
  this itself — `os.environ.setdefault("SSL_CERT_FILE", certifi.where())`
  before importing `whisper` — so no manual `export` is needed; an
  operator-set `SSL_CERT_FILE` still wins via `setdefault`.
- **Whisper needs an audio stream.** `transcribe_video()` returns `[]` for
  a video with no audio track at all (checked via
  `aifun.utils.media.has_audio_stream`) instead of letting whisper's own
  ffmpeg-based audio extraction raise — matters for silent screen
  recordings and for this project's own silent synthetic test fixtures.
- **Model weights cache at `engine/data/cache/whisper/`** (already
  gitignored under `engine/data/**`) — first run downloads (~72MB for
  `tiny`), later runs/tests reuse it.
- **No true-positive face-detection test.** `test_analysis.py` only
  asserts *no* face is found on synthetic (non-face) ffmpeg patterns —
  there's no real face image checked in to assert a true positive against.

## 4. Test coverage

`engine/tests/test_transcribe.py`, `test_analysis.py`, `test_photo_score.py`,
`test_cli.py` — all exercise the real `ffmpeg`/Whisper/OpenCV/PySceneDetect
code paths (no mocking), same approach as `test_assemble.py` from Phase 2.
Run with `pytest` per `docs/phase1-data-ingestion.md`'s "Running tests".

## 5. Next: Phase 4

Swap `aifun.editing.highlights.build_fixture_highlight()` (Phase 2's
hand-authored stand-in, called from `aifun/assemble.py`) for
`aifun.analysis.find_highlights()` + `aifun.transcribe.transcribe_video()`
in the actual upload → process pipeline, plus caption burn-in and audio
normalize (both still `NotImplementedError` stubs in `aifun/editing/`). See
`docs/progress.md` §5.
