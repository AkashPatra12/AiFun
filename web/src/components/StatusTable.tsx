import { useState } from "react";
import {
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getMediaOutputUrl,
  listMedia,
  processMedia,
  type MediaDto,
} from "@/api/media";
import { MediaPreviewModal } from "@/components/MediaPreviewModal";

// Table re-fetches on an interval so `processing` rows flip to
// `processed`/`failed` without a manual page refresh (see
// docs/phase1-data-ingestion.md §2).
const POLL_INTERVAL_MS = 2000;

export function StatusTable() {
  const queryClient = useQueryClient();
  const [previewMedia, setPreviewMedia] = useState<MediaDto | null>(null);

  const { data: media = [], isLoading } = useQuery({
    queryKey: ["media"],
    queryFn: listMedia,
    refetchInterval: POLL_INTERVAL_MS,
  });

  // "uploading" is a client-only optimistic state for a POST /media still in
  // flight — it has no row in Postgres yet, so it isn't in `media` above.
  const pendingUploads = useMutationState({
    filters: { mutationKey: ["uploadMedia"], status: "pending" },
    select: (mutation) => mutation.state.variables as File,
  });

  const processMutation = useMutation({
    mutationFn: processMedia,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["media"] }),
  });

  if (isLoading) {
    return <p className="text-sm text-neutral-500">Loading…</p>;
  }

  const hasRows = media.length > 0 || pendingUploads.length > 0;

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Filename</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {!hasRows && (
            <TableRow>
              <TableCell colSpan={3} className="text-center text-neutral-400">
                No media yet — upload a video or photo above.
              </TableCell>
            </TableRow>
          )}

          {pendingUploads.map((file, i) => (
            <TableRow key={`uploading-${i}-${file.name}`}>
              <TableCell>{file.name}</TableCell>
              <TableCell>
                <StatusBadge status="uploading" />
              </TableCell>
              <TableCell />
            </TableRow>
          ))}

          {media.map((item) => (
            <TableRow key={item.id}>
              <TableCell>{item.originalFilename}</TableCell>
              <TableCell>
                <StatusBadge status={item.status} />
              </TableCell>
              <TableCell className="flex justify-end gap-2">
                {(item.status === "uploaded" || item.status === "failed") && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={
                      processMutation.isPending &&
                      processMutation.variables === item.id
                    }
                    onClick={() => processMutation.mutate(item.id)}
                  >
                    {item.status === "failed" ? "Retry" : "Process"}
                  </Button>
                )}
                {item.status === "processed" && (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPreviewMedia(item)}
                    >
                      View
                    </Button>
                    <Button size="sm" variant="ghost" asChild>
                      <a href={getMediaOutputUrl(item.id)} download>
                        Download
                      </a>
                    </Button>
                  </>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <MediaPreviewModal
        media={previewMedia}
        onOpenChange={(open) => !open && setPreviewMedia(null)}
      />
    </>
  );
}

function StatusBadge({
  status,
}: {
  status: MediaDto["status"] | "uploading";
}) {
  const styles: Record<string, string> = {
    uploading: "bg-neutral-100 text-neutral-600",
    uploaded: "bg-blue-50 text-blue-700",
    processing: "bg-amber-50 text-amber-700",
    processed: "bg-green-50 text-green-700",
    failed: "bg-red-50 text-red-700",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}
    >
      {(status === "uploading" || status === "processing") && (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      {status}
    </span>
  );
}
