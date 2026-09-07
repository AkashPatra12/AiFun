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
  originalFilename: string;
  mimeType: string;
  sizeBytes: number;
  durationSeconds: number | null;
  width: number | null;
  height: number | null;
  thumbnailKey: string | null;
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

/** URL for streaming the processed file — used for both the <video> preview
 * and the download link (see docs/phase1-data-ingestion.md §7). */
export function getMediaOutputUrl(id: string): string {
  return `${API_BASE_URL}/media/${id}/output`;
}
