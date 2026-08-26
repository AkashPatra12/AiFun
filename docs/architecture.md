# Architecture

## What this does

Takes a long-form video and produces one or more short vertical clips
(reels/shorts): finds the best moments, reframes to 9:16, adds captions,
exports the finished clip + thumbnail. No auto-publishing (yet) — output
is a file you post yourself.

## Pipeline

```
ingest -> transcribe -> analysis -> editing -> render -> export
```

- **ingest** — load the source video (local file or URL) into a working format
- **transcribe** — speech-to-text with timestamps
- **analysis** — use the transcript to find engaging, self-contained segments (highlights)
- **editing** — per highlight: cut the segment, reframe to vertical, burn in captions, normalize audio
- **render** — ffmpeg encode pass
- **export** — write the final clip + thumbnail to `data/output/`

Each stage is its own package under `backend/src/aifun/` so a stage (e.g. the
highlight-detection model, or the reframing method) can be swapped without
touching the others. `pipeline.py` just wires them together in order.

## Frontend

Monorepo: `frontend/` (React + TypeScript, Vite) alongside `backend/`. Will
call into the pipeline to let a user upload a video, review/pick highlights,
and preview generated clips. No API layer between them yet — that's needed
before the frontend can actually drive the pipeline.

## Status

Scaffolded, stages are stubs. Details (model choices, reframing approach,
caption styling, frontend<->backend API) to be filled in as each is built.
