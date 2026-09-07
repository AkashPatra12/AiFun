# Phase 4 — Real highlights in the live pipeline, progress, and resumability

Swaps Phase 2's fixture (`aifun.editing.highlights.build_fixture_highlight`,
now deleted) for Phase 3's real `aifun.analysis.find_highlights` in the
actual upload → process pipeline (`docs/README.md` step 12), plus two
things that only became necessary once real (slower, multi-stage,
sometimes-failing) analysis replaced an instant fixture: visible progress,
and not losing work if the process dies partway through.

---

## 1. Why this bundles three things

Swapping in real highlight detection meant the pipeline went from "one
fast fixed step" to "several slower steps, each of which can fail
independently, run once per candidate." That surfaced two problems the
fixture never had:

1. **The UI's `processing` status told you nothing** — fine when the step
   took under a second; not fine once it might be transcribing for a few
   seconds, then scoring scenes, then rendering up to
   `max_clips_per_video` (5) preview clips.
2. **A crash mid-job was silent and unrecoverable** — the affected `Media`
   row stayed at `status="processing"` forever, and `POST
   /media/{id}/process` only accepts `uploaded`/`failed`, so there was no
   way to even retry it.

Both are addressed by the same underlying change: persisting more state,
more often, during the pipeline — so it doubles as the fix for "don't lose
progress."

## 2. Data model

**`Media.stage`** (nullable `VARCHAR`, added to the existing table via an
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `aifun.db.session.init_db()`
— still no Alembic per `docs/phase1-data-ingestion.md` §1, but this is the
"schema needs to evolve without wiping local data" case that doc's own
§9 flagged as Alembic's trigger point; a raw guarded `ALTER` was simpler
than standing up a migrations tool for one column). One of:

`transcribing` → `detecting_highlights` → `rendering_previews` → `exporting`
→ `null` (done, whether `status` landed on `processed` or `failed`).

**`Highlight`** (new table) — one row per candidate segment for a video
`Media`, matching `contracts/highlight.schema.json` plus rendering state:

| Column | Notes |
|---|---|
| `media_id` | FK to `media.id` (no ORM relationship, just a filtered query) |
| `start_seconds`, `end_seconds`, `score`, `reason` | the contract fields |
| `status` | `pending` → `rendered` / `failed` |
| `clip_key` | path to that highlight's own rendered 9:16 preview clip, once `rendered` |

Photos don't get `Highlight` rows — there's no "scene" to detect in a
still image, so `aifun.processing._process_photo` skips analysis entirely.

## 3. Pipeline (`aifun.processing._process_video`)

```
highlights = existing Highlight rows for this media, if any
if none:
    stage = "transcribing"; commit
    stage = "detecting_highlights"; commit
    detected = aifun.assemble.detect_highlights(...)   # Whisper + find_highlights
    persist one Highlight row per candidate; commit     # <-- crash-safe checkpoint 1

stage = "rendering_previews"; commit
for each highlight, best score first:
    if already status == "rendered": skip                # <-- resumability
    render its own 9:16 preview clip (aifun.render, same building
        blocks Phase 2 used for its one fixture-driven output)
    commit                                                # <-- crash-safe checkpoint 2 (per highlight)

stage = "exporting"; commit
copy the top-scoring *rendered* highlight's clip as Media.output_key
    (no second render — it's already the right cut/reframe/audio-mix)
status = "processed" (or "failed" if no highlight rendered), stage = null
```

Every `commit` above is a point a retry can resume from instead of
redoing work — most importantly, the expensive transcribe + scene-scoring
step only ever runs once per media, even across N retries, because its
output (the `Highlight` rows) is what a retry checks for first.

**On API startup** (`aifun.processing.reconcile_orphaned_jobs`, called from
`app.py`'s `lifespan`): any `Media` still at `status="processing"` means
the previous process died mid-job — Phase 1's in-process thread pool
(`docs/phase1-data-ingestion.md` §1) has no durable queue to resume a job
from automatically. That row is flipped to `failed` (not left stuck
forever) so the existing Process/Retry button works on it — and, per the
resumability above, that retry skips straight to rendering whatever
`Highlight` rows already exist rather than re-transcribing.

## 4. Real-time progress: SSE, not just a poll

`GET /media/{id}/events` — a Server-Sent Events stream
(`aifun.api.routes.media_events`). Internally it's still a poll — of
Postgres, every 0.5s, from within that request's own async generator —
not a DB trigger/`LISTEN`/`NOTIFY` setup; Postgres is already the single
source of truth the background job writes to, so no separate in-memory
event bus is needed to bridge the two. It pushes a new SSE `data:` message
only when the row actually changes, and closes itself once `status` is
`processed`/`failed` or the client disconnects.

The frontend's existing 2s `GET /media` poll (`StatusTable`) is kept
running regardless, as the fallback if a browser/proxy doesn't handle
`text/event-stream` well or the connection drops — `useMediaEvents`
(`web/src/hooks/useMediaEvents.ts`) just pushes updates into the same
`["media"]` query cache the poll already owns, so the two sources can't
disagree about anything, they just race to be first.

One SQLAlchemy gotcha worth flagging: the stream's session is long-lived
across many loop iterations, so a plain repeated `session.get(Media, id)`
would return that session's *own first-ever* cached copy forever — the
background job commits through a completely different session/connection,
which this one has no way to know about otherwise. Fixed with
`session.expire_all()` at the top of each loop iteration.

## 5. Showing what was picked, before later editing

`GET /media/{id}/highlights` lists a video's `Highlight` rows (score
descending). `GET /highlights/{id}/preview` streams one candidate's
rendered clip. In the UI, `HighlightsPanel` (behind a "Show clips" toggle
in `MediaRow`, visible once a video has started processing) lists each
candidate's timestamp range, score, and reason, with an inline `<video>`
once its preview is `rendered` — visible while the job is still running,
not gated behind final completion, since highlights are persisted and
rendered incrementally per §3.

This intentionally stops at *visibility* — no reordering, trimming, or
picking a different highlight than the auto-selected top-scorer from the
UI yet. That's Phase 7 (the timeline editor); this phase's job was making
sure the data it'll need (persisted candidates with real timestamps, and
something to look at for each) already exists.

## 5a. Multi-select, bulk actions, and delete

`StatusTable` gained a checkbox per row (`MediaRow`) plus a header
"select all." With at least one row checked:

- A **"Process selected"** button triggers `POST /media/{id}/process` for
  every checked row that's actually eligible (`uploaded`/`failed` —
  silently skips the rest, same 409 rule the single-row Process/Retry
  button already follows).
- A **"Delete selected"** button, and a per-row **Delete** button
  regardless of selection, both backed by `DELETE /media/{id}`
  (`aifun.api.routes.delete_media`): removes the `Media` row, all its
  `Highlight` rows, and every file they point to (input, output, each
  highlight's preview clip) — best-effort `unlink`, so an already-missing
  file doesn't block the rest. Refused with `409` while `status ==
  "processing"`, same reasoning as not letting `POST .../process` fire
  twice — don't pull a row out from under the background job still writing
  to it.
- `ClipSelectionsSection` renders below the table whenever any *video* is
  checked — one `HighlightsPanel` per checked video, each under its own
  filename heading. Checked photos count toward the buttons above but
  contribute nothing here (no highlights to show). This is deliberately a
  separate section from any single row, so checking several videos and
  hitting "Process selected" gives one place to review all of their
  detected clips at once, not one collapsible toggle per row.

## 6. Test coverage

- `engine/tests/test_processing_pipeline.py` — the full pipeline via
  `_run_processing` directly (real ffmpeg/Whisper, a real `Media` row):
  highlights get persisted and rendered, the top one becomes the output,
  and a simulated retry re-detects nothing and re-renders nothing already
  done.
- `engine/tests/test_highlights_and_sse.py` — the two new routes, plus the
  SSE stream: closes immediately for an already-terminal row, and (via a
  background thread flipping the row mid-stream) actually pushes both the
  `processing` and `processed` states well inside the UI's 2s poll window.
- `web/src/hooks/useMediaEvents.test.tsx`, `HighlightsPanel.test.tsx`, and
  the extended `StatusTable.test.tsx` (now also covering checkboxes, bulk
  process/delete, and per-row delete) cover the frontend side, with a
  stubbed global `EventSource` (`web/src/test/setup.ts`) since jsdom
  doesn't implement it.
- `test_delete_media_*` in `test_media_routes.py` cover the delete
  endpoint: 404, the 409-while-processing guard, and that both the row and
  its input file are actually gone afterward (not just a 204 response).

Both `aifun.processing._run_processing` and the SSE stream's generator
deliberately open their *own* DB session — this is realistic (mirrors how
the real background thread pool and a real browser connection behave) but
means the usual transaction-rollback test isolation (`db_session` in
`conftest.py`) doesn't apply to them; see `make_real_media` in
`conftest.py` for the alternative (a real committed row, cleaned up after).

## 6a. Docker gotcha hit while building this

`docker compose build <service>` only builds the *image* — it does not
touch the running *container*, which keeps running whatever image it was
created from until something recreates it (`up -d`, or `up -d
--force-recreate` if Compose doesn't otherwise detect the image changed).
Built a new `api` image mid-session, kept editing `routes.py` afterward
without re-running `up -d`, and only noticed the running container was
still serving the pre-edit routes when `DELETE /media/{id}` 404'd despite
being right there in the source. Rule of thumb: after `docker compose
build`, always follow with `up -d` (or just `up -d --build`, one step) for
the same service before trusting `curl`/manual testing against it.

## 7. What changed vs. what pre-existing docs said

- `docs/phase3-understand.md` §5 said this swap was "next," not yet done —
  it's done now, along with progress/resumability, which weren't
  anticipated as part of it going in.
- `docs/progress.md`'s deviations table row "Highlight selection (live
  pipeline)" is resolved — real scoring now drives the live pipeline, not
  only the CLI.
