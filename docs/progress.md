# Development Progress

Last updated: 2026-09-07. Tracks status against the features and
Step-by-Step Build Guide in `docs/README.md`, and the local-dev deviations
recorded in `docs/phase1-data-ingestion.md`.

---

## 1. Snapshot

Upload a video/photo through the web UI → it's ingested, ffprobed, and
stored → for a video, transcribed (real Whisper) and scene/highlight-scored
(real `aifun.analysis.find_highlights`, not a fixture) → each candidate
highlight gets its own rendered 9:16 preview clip, with the top-scoring one
becoming the main output. Progress pushes live to the UI via SSE
(`GET /media/{id}/events`), and detected clips are visible — timestamps,
score, reason, and their own preview — in a dedicated section as soon as
they're persisted, not gated behind full completion. Rows can be
multi-selected (checkboxes), bulk-processed, and deleted (cascading to
their highlights and every file on disk). A crashed job is recoverable: a
retry resumes from whatever was already detected/rendered rather than
starting over. Postgres, the engine API, and the web SPA all run under one
`docker compose up --build`.

**Not yet started:** trend intelligence (`docs/README.md` features #2, #5),
caption burn-in and audio normalize (`editing/captions.py`,
`editing/audio.py::normalize` — still stubs), auth/projects, and the
timeline editor (reorder/trim/swap/regenerate a clip).

---

## 2. Feature checklist (`docs/README.md` §1)

| # | Feature | Status |
|---|---|---|
| 1 | Media ingestion | ✅ Done — upload, local-filesystem storage, `ffprobe` metadata |
| 2 | Trend radar | ⬜ Not started (`trend/scrape.py`, `trend/cache.py` — stubs) |
| 3 | Smart clip selection | ✅ Done (heuristic, not ML/LLM) — `aifun.analysis.find_highlights` drives the live pipeline; every candidate persisted + rendered + visible in the UI, see `docs/phase4-smart-editing.md` |
| 4 | Photo scoring | 🟡 Partial — `aifun.analysis.photo_score` (sharpness/exposure/face) exists, CLI-only, not surfaced in the API/UI |
| 5 | Beat-synced cutting | ⬜ Not started (`trend/beat.py` — stub) |
| 6 | Auto captions | 🟡 Partial — transcription done (`aifun.transcribe`, real Whisper); caption burn-in itself (`editing/captions.py`) still a stub |
| 7 | Auto assembly | 🟡 Partial — crop/resize to 9:16 ✅, fixed audio mix ✅, real highlight selection ✅; transitions, text overlays, real trend-synced mixing not started |
| 8 | Preview & edit | 🟡 Partial — upload + status table with multi-select/bulk-process/delete, View/Download, and a live clip-selections panel; no timeline (reorder/trim/swap/regenerate) yet |
| 9 | Job queue + status | 🟡 Partial — in-process background task (not Celery/RQ + Redis, see §4) but with per-stage progress (SSE), crash recovery, and resumable retries |
| 10 | Auth & projects | ⬜ Not started |
| 11 | *(stretch)* Auto-publish | ⬜ Not started |

---

## 3. Build guide checklist (`docs/README.md` §5)

- [x] **Phase 0 — Setup**: repo layout, frozen contracts
      (`contracts/*.schema.json`), `docker-compose.yml`
- [x] **Phase 1 — Upload UI**, done, but not as specified: a real
      upload/status UI shipped directly against the real local API; the
      doc's *mocked*-API-first approach was intentionally skipped since one
      person owns both sides for this slice
- [x] **Phase 2 — Basic pipeline MVP**: FastAPI app (auth pending), media
      upload, job trigger, FFmpeg pipeline (cut → reframe to 9:16 → mix
      fixed audio → export), status written to Postgres, UI polls
      `GET /media` — see `docs/phase1-data-ingestion.md` §13
- [x] **Phase 3 — Understand MVP**: real Whisper transcription, scene +
      transcript highlight scoring, photo aesthetic scoring — see
      `docs/phase3-understand.md`
- [x] **Phase 4 — Smart editing**: real `find_highlights` output (not the
      Phase 2 fixture, now deleted) drives the live pipeline, with
      per-candidate previews, SSE progress, and crash-resumable retries —
      see `docs/phase4-smart-editing.md`. Caption burn-in and audio
      normalize are the parts of this phase still outstanding
      (`editing/captions.py`, `editing/audio.py::normalize` — stubs)
- [ ] **Phase 5 — Trend intelligence**: scraper, trend cache, librosa beat
      detection
- [ ] **Phase 6 — Beat-synced cutting**: consume `trend.json` for cut points
- [ ] **Phase 7 — Editing & polish**: timeline UI, style presets — the
      per-candidate highlight data/previews Phase 4 built are exactly what
      this needs to consume
- [ ] **Phase 8 — Publishing** *(stretch)*: Instagram/TikTok posting APIs

---

## 4. Known deviations from `docs/README.md`

Carried forward from `docs/phase1-data-ingestion.md` §9 — these are
intentional local-dev simplifications, not a change in target architecture:

| Topic | `docs/README.md` target | Current state |
|---|---|---|
| Object storage | Supabase Storage / Cloudflare R2 | Local filesystem (`engine/data/`) |
| Job queue | Celery/RQ + Redis | In-process thread pool (`processing.py`), now with SSE progress + crash recovery + resumable retries (`docs/phase4-smart-editing.md`) — narrows the gap but isn't a real durable queue |
| API build order | UI built against a mocked Engine API first | UI built directly against the real local API |
| Data model | `projects`/`jobs` tables, `POST /jobs` with `mediaIds[]` | Single `media` table (+ `highlights`), one row = one upload = one job |
| Schema migrations | Alembic | Still none — `Media.stage`, the one column added post-launch, used a guarded `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `init_db()` instead; see `docs/phase4-smart-editing.md` §2 |

Revisit the job-queue row before scaling past one process/one machine —
that's the point `trigger_processing`/`schedule_processing` needs to become
a real queue push instead of a function call.

---

## 5. Next steps (checklist, priority order)

- [x] **Tests** — `engine/tests/` (38 pytest cases) and
      `web/src/**/*.test.{ts,tsx}` (24 Vitest cases) — run with `pytest`
      (from `engine/`, venv active) and `pnpm test` (from `web/`)
- [x] **Fix**: photo uploads returned `durationSeconds: 0.04` instead of
      `null` — `aifun.ingest.ingest_upload` now nulls it out for `kind="photo"`
- [x] **Phase 4 — Real highlights in the live pipeline** — plus real-time
      progress (SSE), crash recovery (`reconcile_orphaned_jobs`), resumable
      retries, a `highlights` table + endpoints, and UI: multi-select,
      bulk process/delete, per-row delete, a live clip-selections panel —
      see `docs/phase4-smart-editing.md`
- [ ] **Caption burn-in + audio normalize** — the two Phase 4 pieces still
      outstanding (`editing/captions.py`, `editing/audio.py::normalize`)
- [ ] **Photo scoring in the live pipeline** — `aifun.analysis.photo_score`
      exists (CLI-only); nothing calls it from `_process_photo` or surfaces
      a score in the API/UI yet
- [ ] **Auth + projects** — `projects`/`jobs` tables, `POST /jobs` job
      intake matching `contracts/render-job.schema.json`, scoping `media`
      rows to a project (currently `projectId` is deliberately omitted, per
      `docs/phase1-data-ingestion.md` §1)
- [ ] **Phase 5 — Trend intelligence** — can start any time, independent of
      the above: scraper, trend cache, librosa beat detection, to
      eventually replace `engine/assets/music/fixture_track.mp3`
- [ ] **Phase 7 — Timeline editor UI** — reorder/trim/swap clips, regenerate
      a single segment, style presets; let a person pick a highlight other
      than the auto-selected top-scorer as the main output
- [ ] **Job queue migration** — swap the in-process thread pool for
      Celery/RQ + Redis once running on more than one machine/process
