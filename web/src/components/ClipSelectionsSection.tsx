import { HighlightsPanel } from "@/components/HighlightsPanel";
import type { MediaDto } from "@/api/media";

interface ClipSelectionsSectionProps {
  selectedMedia: MediaDto[];
}

/** The smart-clip candidates for every currently-checked video, in one
 * dedicated section below the table — separate from any single row, so
 * picking several videos at once and hitting "Process selected" gives one
 * place to review what got detected for all of them. Photos are selectable
 * too (for bulk process/delete) but have no highlights, so they're left
 * out here rather than shown as an empty section. */
export function ClipSelectionsSection({ selectedMedia }: ClipSelectionsSectionProps) {
  const videos = selectedMedia.filter((media) => media.kind === "video");

  if (videos.length === 0) {
    return null;
  }

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-neutral-200 p-4">
      <h2 className="text-sm font-semibold text-neutral-900">
        Clip selections
      </h2>
      {videos.map((media) => (
        <div key={media.id} className="flex flex-col gap-1">
          <p className="truncate text-sm font-medium text-neutral-700">
            {media.originalFilename}
          </p>
          {media.status === "uploaded" ? (
            <p className="text-sm text-neutral-400">
              Not processed yet — click Process to detect clips.
            </p>
          ) : (
            <HighlightsPanel mediaId={media.id} />
          )}
        </div>
      ))}
    </section>
  );
}
