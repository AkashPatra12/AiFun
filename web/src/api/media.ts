export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** Server-side status values (see docs/phase1-data-ingestion.md §6).
 * "uploading" is a client-only optimistic state, not part of this union. */
export type MediaStatus = "uploaded" | "processing" | "processed" | "failed";
export type MediaKind = "video" | "photo";

export interface MediaDto {
  id: string;
  kind: MediaKind;
  status: MediaStatus;
  /** Sub-status while status === "processing" (e.g. "transcribing",
   * "detecting_highlights", "rendering_previews", "exporting") — null
   * outside of an active processing run. Kept as a loose string client-side
   * rather than a union so an unrecognized future stage still renders
   * (falls back to the raw value) instead of a type error. */
  stage: string | null;
  originalFilename: string;
  mimeType: string;
  sizeBytes: number;
  durationSeconds: number | null;
  width: number | null;
  height: number | null;
  thumbnailKey: string | null;
  createdAt: string;
}

export type HighlightStatus = "pending" | "rendered" | "failed";

/** A candidate smart-clip segment for a video Media row (see
 * contracts/highlight.schema.json and docs/phase4-smart-editing.md) — one
 * of possibly several; the highest-scoring `rendered` one is what
 * GET /media/{id}/output serves as the main result. */
export interface HighlightDto {
  id: string;
  mediaId: string;
  startSeconds: number;
  endSeconds: number;
  score: number;
  reason: string;
  status: HighlightStatus;
  clipKey: string | null;
  createdAt: string;
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: string };
    return body.detail ?? res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function uploadMedia(
  file: File,
  kind: MediaKind,
  autoProcess: boolean,
): Promise<MediaDto> {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  form.append("autoProcess", String(autoProcess));

  const res = await fetch(`${API_BASE_URL}/media`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }
  return res.json();
}

export async function listMedia(): Promise<MediaDto[]> {
  const res = await fetch(`${API_BASE_URL}/media`);
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }
  return res.json();
}

export async function processMedia(id: string): Promise<MediaDto> {
  const res = await fetch(`${API_BASE_URL}/media/${id}/process`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }
  return res.json();
}

/** Deletes a media row, its highlight rows, and every file they reference
 * (input, output, and each highlight's preview clip). Refused with a 409
 * while status === "processing" — see aifun.api.routes.delete_media. */
export async function deleteMedia(id: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/media/${id}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }
}

/** URL for streaming the processed file — used for both the <video> preview
 * and the download link (see docs/phase1-data-ingestion.md §7). */
export function getMediaOutputUrl(id: string): string {
  return `${API_BASE_URL}/media/${id}/output`;
}

export async function listHighlights(mediaId: string): Promise<HighlightDto[]> {
  const res = await fetch(`${API_BASE_URL}/media/${mediaId}/highlights`);
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }
  return res.json();
}

/** URL for streaming one highlight's rendered 9:16 preview clip. */
export function getHighlightPreviewUrl(highlightId: string): string {
  return `${API_BASE_URL}/highlights/${highlightId}/preview`;
}

/** URL for the Server-Sent Events stream of one media's status/stage —
 * see aifun.api.routes.media_events and useMediaEvents. */
export function getMediaEventsUrl(id: string): string {
  return `${API_BASE_URL}/media/${id}/events`;
}
