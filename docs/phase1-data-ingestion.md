# Phase 1 — Data Ingestion (UI + API)

Scope: the Upload UI and the ingestion API only. Core Processing (transcribe,
analysis, trend) is owned by a different dev and is out of scope here except
as the consumer of what this slice produces, and as the thing this slice's
"Process" action and status table surface the result of.

This is a **local-only, no-cloud** phase — everything in this doc runs on
one machine, no hosted services. It deliberately diverges from
`docs/README.md`'s Phase 1/2 (which assume a mocked API and cloud object
storage) — see [§9, Deviations from docs/README.md](#9-deviations-from-docsreadmemd).

---

## 1. Scope decisions (already made)

- UI talks to a **real local API** directly — no MSW mock layer, since the
  same person owns both sides for this slice.
- Media bytes are stored on the **local filesystem** (`engine/data/input/`
  for uploads, `engine/data/output/` for processed results — both already
  exist and are gitignored).
- **Metadata/status store: Postgres, run in Docker** (via `docker-compose.yml`).
  Docker Desktop is already installed; a container gives both devs an
  identical, easily-reset DB with no host install/version drift. This also
  matches `docs/README.md`'s own Phase 0 plan, so it's not actually a
  deviation from the doc.
- **No Redis / no separate worker.** Ingestion and Core Processing run as
  **one service/process** for Phase 1. Processing is triggered via an
  **in-process background task** (thread pool) — not a queue message, not
  polling — either automatically right after upload, or manually later (see
  [§2](#2-ui-upload--status-table)). Accepted tradeoff: a job in flight is
  lost if the server restarts mid-processing; fine for a single-user local
  tool. Keep the trigger behind one function (e.g.
  `trigger_processing(media_id)`) so swapping in a real queue/separate
  service later doesn't touch the ingestion route.
- **Upload is a single API call.** One `multipart/form-data POST /media`
  carries the file bytes and metadata (`kind`, `autoProcess`) together — no
  presigned-URL, multi-step dance, since the API itself writes to the local
  filesystem instead of routing bytes around itself to cloud storage.
- **`projectId` omitted for Phase 1** — no auth/projects UI exists yet, so
  there's no real project to scope media to. Add the column when auth/
  projects land.
- **No client-side upload size/duration cap for Phase 1** — add validation
  once real usage shows what's reasonable.
- **Schema lives in code, no migrations tool.** `engine/src/aifun/db/models.py`
  (the `Media` model) is the schema; `engine/src/aifun/db/session.py` holds
  the SQLAlchemy engine/session setup reading `DATABASE_URL`. The app calls
  `Base.metadata.create_all()` on startup — no Alembic, no versioned
  migration scripts, for one table with no production data to preserve yet.
  Add Alembic when the schema needs to evolve without wiping local data.
  `docker-compose.yml` (the Postgres container itself) stays at repo root.
- **`trigger_processing(media_id)` is a placeholder for Phase 1**, not the
  real Core Processing pipeline (which is still mostly `NotImplementedError`
  stubs from the original scaffold). The placeholder copies the input file
  to the output path unchanged (with a short simulated delay) and marks
  `status="processed"` — this makes upload → process → view → download
  fully testable on its own, without waiting on Core Processing's real
  logic to land. Swap the placeholder body for the real pipeline call once
  that code exists; the function signature/seam doesn't change.
- **`engine/src/aifun/worker/webhook.py`** (leftover from before the project
  moved to polling, and now further orphaned since Phase 1 has no separate
  worker/queue at all) is left untouched — out of scope for this slice.
- **Frontend setup done now, not deferred:** bump `web/package.json` React
  18.3.1 → 19 (cheap now, before real components exist), and set up
  Tailwind + shadcn/ui from the start per `docs/README.md`'s stated stack,
  rather than starting with plain CSS and retrofitting later.

### Prerequisite

`ffmpeg`/`ffprobe` must be installed as a system binary (not a pip package)
— installed via `brew install ffmpeg` (v9.0.1), confirmed working.

## 2. UI: upload + status table

Single page. Two parts:

**Upload control:** file picker/drag-drop, a **"Start processing on
upload"** checkbox (**checked by default**), and a submit action.

**Status table**, below the upload control, listing every `Media` row:

| Column | Notes |
|---|---|
| Filename | `original_filename` |
| Status | `uploading` \| `uploaded` \| `processing` \| `processed` \| `failed` |
| Actions | depends on status, see below |

`uploading` is a **client-only, optimistic UI state** — shown while the
`POST /media` request is in flight, before the server has created the row at
all. It is not a `Media.status` value in Postgres (see [§6](#6-what-the-api-stores)).

Per-row actions by status:

| Status | Action(s) shown |
|---|---|
| `uploaded` (uploaded, not yet processed — `autoProcess` was unchecked, or nothing's been triggered yet) | **Process** button → `POST /media/{id}/process` |
| `processing` | none — show a spinner/disabled state |
| `processed` | **View** (opens the processed video in a modal with a native `<video>` player) and **Download** (`<a href="/media/{id}/output" download>`) |
| `failed` | **Process** button again, reusing the same manual-trigger endpoint as a retry — no separate retry endpoint needed |

The table re-fetches (`GET /media`) on an interval so `processing` rows flip
to `processed`/`failed` without a manual page refresh.

## 3. Data flow

```
1. User picks/drops a file, optionally toggles "Start processing on upload"
2. UI -> POST /media  (single multipart request: file bytes + kind + autoProcess)
   API -> saves bytes to engine/data/input/{media_id}.{ext}
        -> ffprobes the file server-side (duration, width, height — never
           trust client-reported values)
        -> writes a Media row to Postgres, status="uploaded"
        -> if autoProcess: schedules trigger_processing(media_id) as an
           in-process background task (thread pool) — does NOT block the
           response
        -> returns { id, filename, kind, status, createdAt, ... } immediately
3. UI -> GET /media  (polled) -> list of Media rows, rendered in the status
   table
4a. If autoProcess was true, or the user later clicks Process:
    UI -> POST /media/{id}/process  (only valid when status is "uploaded" or
         "failed")
    API -> schedules trigger_processing(media_id) (same function as step 2)
         -> flips status to "processing"
4b. In the background, on the same process: Core Processing's code runs via
    trigger_processing(), writes the result to engine/data/output/{media_id}.mp4,
    sets output_key, and flips status to "processed" (or "failed") in the
    same Postgres row — the UI sees this on its next GET /media poll
5. UI -> GET /media/{id}/output  -> streams the processed file, used for
   both the "View" modal (<video src=...>) and the "Download" link
```

No presigned-URL step: because storage is local, the API can accept the
multipart upload directly instead of issuing a presigned URL to cloud
storage (the pattern `docs/README.md` describes for the cloud target).

No queue/worker hop either: because ingestion and Core Processing share one
process for Phase 1, steps 4a/4b are function calls, not a network hop or a
Redis message.

## 4. What the UI accepts

- Video: `.mp4` / `.mov`
- Photo: `.jpg` / `.png`
- No client-side size/duration cap in Phase 1 — see [§1](#1-scope-decisions-already-made).

## 5. What the UI passes to the API

**`POST /media`** — single multipart request:

| field | type | notes |
|---|---|---|
| `file` | binary | the raw video/photo bytes |
| `kind` | `"video"` \| `"photo"` | |
| `autoProcess` | boolean | from the upload checkbox; default `true` |

**`POST /media/{id}/process`** — no body. Only valid when the row's status
is `uploaded` or `failed`; used for the manual "Process" action and for
retries.

No `projectId` and no size/duration limits in Phase 1 — see [§1](#1-scope-decisions-already-made).

## 6. What the API stores

A `Media` record in Postgres:

| field | notes |
|---|---|
| `id` | media id, uuid |
| `storage_key` | local input path, e.g. `engine/data/input/{id}.mp4` |
| `output_key` | local output path once processed, e.g. `engine/data/output/{id}.mp4`; null until `status="processed"` |
| `kind` | video / photo |
| `status` | `uploaded` → `processing` → `processed` / `failed` (server-side values only — `uploading` is UI-only, see [§2](#2-ui-upload--status-table)) |
| `original_filename`, `mime_type`, `size_bytes` | client-reported, informational only |
| `duration_seconds`, `width`, `height` | server-verified via `ffprobe`, null until processed |
| `thumbnail_key` | filled in later (not in this slice's scope) |
| `created_at` | |

API responses use camelCase, friendlier names (`filename`, `createdAt`) —
not a 1:1 serialization of the snake_case columns above (`original_filename`,
`created_at`). This is a deliberate response-schema mapping (e.g. a pydantic
model with an alias generator), not a second source of truth — the table
above is the only schema; the wire format is just its JSON casing.

Filename convention on disk: `{media_id}.{ext}` only — no other metadata
encoded in the filename or path. Mutable fields (status, scores, duration)
live only in the Media record, never in the filename — even though Phase 1
runs ingestion and processing as one process (see [§1](#1-scope-decisions-already-made)),
renaming files to reflect status would still race against a concurrent
`GET /media/{id}/output` request reading the same path while the background
task is still writing it.

## 7. Serving the processed output

**`GET /media/{id}/output`** streams the file at `output_key` (only valid
once `status="processed"`). Used two ways by the same endpoint:
- **View:** a modal with `<video src="/media/{id}/output" controls>`.
- **Download:** a plain `<a href="/media/{id}/output" download>`.

No separate thumbnail/preview pipeline in this slice — the modal plays the
actual processed file.

## 8. Error responses

Status codes for the invalid-state and invalid-input cases referenced in
§5–§7 (decided during step 6+7 implementation, not fully specified above):

| Case | Route(s) | Status |
|---|---|---|
| `media_id` doesn't exist | `POST /media/{id}/process`, `GET /media/{id}/output` | `404 Not Found` |
| `media_id` exists but is in the wrong status for the action (`process` called while `processing`/`processed`; `output` requested before `status="processed"`) | `POST /media/{id}/process`, `GET /media/{id}/output` | `409 Conflict` |
| `kind`/file-extension mismatch, or extension not in the accepted set (§4) | `POST /media` | `400 Bad Request` |

`POST /media/{id}/process` remains valid from both `uploaded` and `failed`
(retry), per §2 — the 409 above only fires from `processing`/`processed`.

## 9. Deviations from docs/README.md

| Topic | docs/README.md says | This doc says (Phase 1) |
|---|---|---|
| Object storage | Supabase Storage / Cloudflare R2, presigned URLs (Phase 2, step 6) | Local filesystem, direct multipart upload |
| Metadata DB | Postgres via Docker Compose (Phase 0) / Supabase Postgres (prod) | **Matches** — Postgres via Docker Compose, no deviation |
| Job queue | Celery/RQ + Redis, even within the single Reel Engine service | No Redis for Phase 1 — in-process background task instead |
| API build order | UI built against a **mocked** Engine API first (Phase 1), real API lands from Dev A2 later | UI built directly against the real local ingestion API, since one person owns both |

These are intentional simplifications for local dev, not a redesign of the
target architecture. Before scaling past one process/one machine, revisit
the Job queue row and swap the in-process trigger for Celery/RQ + Redis —
that's the point at which `trigger_processing(media_id)` (see §1) needs to
become a queue push instead of a function call.

## 10. Local dev tooling (informational, not architecture)

- Postgres runs in Docker (Docker Desktop already installed).
- DB inspection: Microsoft's official **PostgreSQL** VS Code extension
  (`ms-ossdata.vscode-pgsql`), connecting to `localhost:5432` once the
  compose file publishes that port.

### Running the backend locally

```bash
# from repo root — bring up Postgres if it isn't already running
docker compose up -d

# from engine/
source .venv/bin/activate
uvicorn aifun.api.app:app --reload --port 8000
```

`/docs` (Swagger UI) is served at `http://localhost:8000/docs`. Smoke-test
an upload with a throwaway synthetic clip (no need for a real sample file —
see [§ seed data](#seed-test-data) below for why one isn't checked in):

```bash
ffmpeg -f lavfi -i testsrc=duration=2:size=320x240:rate=10 -y /tmp/sample.mp4 -loglevel error
curl -X POST http://localhost:8000/media \
  -F "file=@/tmp/sample.mp4;type=video/mp4" \
  -F "kind=video" \
  -F "autoProcess=true"
```

Poll `GET /media` a couple seconds later to see `status` flip to
`"processed"`, then fetch `GET /media/{id}/output`.

To exercise the photo path (`durationSeconds` should come back `null`,
`width`/`height` still populated):

```bash
ffmpeg -f lavfi -i color=c=blue:s=640x480 -frames:v 1 -y /tmp/sample.jpg -loglevel error
curl -X POST http://localhost:8000/media \
  -F "file=@/tmp/sample.jpg;type=image/jpeg" \
  -F "kind=photo" \
  -F "autoProcess=true"
```

### Connecting the VS Code Postgres extension

1. Install `ms-ossdata.vscode-pgsql` (Microsoft's official PostgreSQL
   extension).
2. Open its sidebar → **New Connection** → **Parameters** tab.
3. Fill in (values match [engine/.env](../engine/.env)):
   - **Server name:** `localhost` — **not** `localhost:5432`; the field
     resolves this as a literal hostname, so appending the port here fails
     with `nodename nor servname provided`. Set the port under **Advanced**
     if there's no separate port field (default `5432` otherwise).
   - **Authentication type:** Password
   - **User name:** `aifun`
   - **Password:** `aifun`
   - **Database name:** `aifun`
4. **Test Connection**, then **Save & Connect**.
5. Browse data: expand **connection → Databases → `aifun` → Schemas →
   `public` → Tables → `media`**, right-click → "Select Top N Rows". Or
   open a new query against the connection and run
   `SELECT * FROM media ORDER BY created_at DESC;`.

### Seed test data {#seed-test-data}

No sample video is checked into the repo — `engine/data/input/` is
gitignored anyway (see [.gitignore](../.gitignore)), and a real media file
would be repo-bloating binary content for something fully reproducible on
demand. Use the one-line `ffmpeg testsrc` command above to generate a
throwaway clip for manual testing instead.

## 11. Build order

Backend first, verified standalone, before any frontend work — so a broken
UI is never masking a broken API.

**Backend**
1. New git branch for this slice (changes stay uncommitted until reviewed —
   commit only when asked).
2. `docker-compose.yml` (Postgres) — bring it up, confirm reachable.
3. `engine/src/aifun/db/session.py` + `models.py` (`Media` model) —
   `create_all()` on startup.
4. FastAPI app skeleton (`api/app.py`) — CORS for `localhost:5173`, mounts
   routes, runs the DB startup hook.
5. Filesystem + `ffprobe` helpers — save-to-disk, extract duration/width/height.
6. Routes in order: `POST /media` → `GET /media` → `POST /media/{id}/process`
   → `GET /media/{id}/output`.
7. `trigger_processing()` placeholder (passthrough copy + simulated delay),
   wired via a bounded thread pool.
8. **Verify manually** — `uvicorn` + FastAPI's `/docs` page (or curl): upload
   a real file, confirm `uploaded → processing → processed`, confirm
   `GET /media/{id}/output` serves the file. Don't start the frontend until
   this works standalone.

**Frontend**
9. Bump React 18 → 19; add Tailwind + shadcn/ui + Tanstack Query.
10. `web/src/api/media.ts` — `uploadMedia`, `listMedia`, `processMedia`,
    output URL helper.
11. Upload control (file picker/drag-drop + the checkbox).
12. Status table (polls `GET /media`, per-row actions by status).
13. View modal (native `<video>`) + download link.
14. Wire into `App.tsx` with `QueryClientProvider`.
15. **Verify in the browser** — upload a file, watch it process, view and
    download the result.

Tests are deferred to a follow-up pass (pytest/TestClient for the API,
Vitest for the UI) — this build gets working code first.

## 12. Open questions to close before writing code

None outstanding — all Phase 1 decisions above are final.
