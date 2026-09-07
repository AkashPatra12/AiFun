import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusBadge } from "@/components/StatusBadge";
import { TableCell, TableRow } from "@/components/ui/table";
import { useMediaEvents } from "@/hooks/useMediaEvents";
import { getMediaOutputUrl, type MediaDto } from "@/api/media";

interface MediaRowProps {
  media: MediaDto;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
  onView: (media: MediaDto) => void;
  onProcess: (id: string) => void;
  onDelete: (id: string) => void;
  isProcessPending: boolean;
  isDeletePending: boolean;
}

export function MediaRow({
  media,
  isSelected,
  onToggleSelect,
  onView,
  onProcess,
  onDelete,
  isProcessPending,
  isDeletePending,
}: MediaRowProps) {
  useMediaEvents(
    media.id,
    media.status === "uploaded" || media.status === "processing",
  );

  return (
    <TableRow>
      <TableCell>
        <Checkbox
          checked={isSelected}
          onCheckedChange={() => onToggleSelect(media.id)}
          aria-label={`Select ${media.originalFilename}`}
        />
      </TableCell>
      <TableCell>{media.originalFilename}</TableCell>
      <TableCell>
        <StatusBadge status={media.status} stage={media.stage} />
      </TableCell>
      <TableCell className="flex justify-end gap-2">
        {(media.status === "uploaded" || media.status === "failed") && (
          <Button
            size="sm"
            variant="outline"
            disabled={isProcessPending}
            onClick={() => onProcess(media.id)}
          >
            {media.status === "failed" ? "Retry" : "Process"}
          </Button>
        )}
        {media.status === "processed" && (
          <>
            <Button size="sm" variant="outline" onClick={() => onView(media)}>
              View
            </Button>
            <Button size="sm" variant="ghost" asChild>
              <a href={getMediaOutputUrl(media.id)} download>
                Download
              </a>
            </Button>
          </>
        )}
        <Button
          size="sm"
          variant="ghost"
          disabled={media.status === "processing" || isDeletePending}
          onClick={() => onDelete(media.id)}
          className="text-red-600 hover:bg-red-50 hover:text-red-700"
        >
          Delete
        </Button>
      </TableCell>
    </TableRow>
  );
}
