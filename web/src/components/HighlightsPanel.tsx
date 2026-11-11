import { useQuery } from "@tanstack/react-query";

import { getHighlightPreviewUrl, listHighlights } from "@/api/media";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** The smart-clip candidates detected for one video — visible while a job
 * is still mid-run (they're persisted and rendered incrementally, see
 * aifun.processing._process_video) as well as once it's done, so a person
 * can see what was picked and why before any later editing happens. */
export function HighlightsPanel({ mediaId }: { mediaId: string }) {
  const { data: highlights = [] } = useQuery({
    queryKey: ["highlights", mediaId],
    queryFn: () => listHighlights(mediaId),
    // Backstop for the same reason StatusTable polls GET /media — SSE
    // (useMediaEvents) already invalidates this on every push.
    refetchInterval: 2000,
  });

  if (highlights.length === 0) {
    return (
      <p className="py-2 text-sm text-neutral-400">Detecting highlights…</p>
    );
  }

  return (
    <ul className="flex flex-col gap-2 py-2">
      {highlights.map((highlight) => (
        <li key={highlight.id} className="flex items-center gap-3 text-sm">
          <span className="w-24 shrink-0 font-mono text-xs text-neutral-600">
            {formatTimestamp(highlight.startSeconds)}–
            {formatTimestamp(highlight.endSeconds)}
          </span>
          <span className="w-20 shrink-0 text-xs text-neutral-500">
            score {highlight.score.toFixed(2)}
          </span>
          <span className="flex-1 truncate text-xs text-neutral-500">
            {highlight.reason}
          </span>
          {highlight.status === "rendered" ? (
            <video
              src={getHighlightPreviewUrl(highlight.id)}
              controls
              preload="none"
              className="h-14 w-8 shrink-0 rounded bg-black object-cover"
            />
          ) : (
            <span className="shrink-0 text-xs text-neutral-400">
              {highlight.status}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
