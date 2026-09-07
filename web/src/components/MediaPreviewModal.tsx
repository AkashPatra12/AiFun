import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getMediaOutputUrl, type MediaDto } from "@/api/media";

interface MediaPreviewModalProps {
  media: MediaDto | null;
  onOpenChange: (open: boolean) => void;
}

/** "View" opens the processed video in a modal with a native <video> player
 * (docs/phase1-data-ingestion.md §2) — no separate thumbnail/preview
 * pipeline, it just plays the actual processed file (§7). */
export function MediaPreviewModal({
  media,
  onOpenChange,
}: MediaPreviewModalProps) {
  return (
    <Dialog open={media !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        {media && (
          <>
            <DialogHeader>
              <DialogTitle>{media.originalFilename}</DialogTitle>
            </DialogHeader>
            {media.kind === "video" ? (
              <video
                src={getMediaOutputUrl(media.id)}
                controls
                autoPlay
                className="w-full rounded-md bg-black"
              />
            ) : (
              <img
                src={getMediaOutputUrl(media.id)}
                alt={media.originalFilename}
                className="w-full rounded-md"
              />
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
