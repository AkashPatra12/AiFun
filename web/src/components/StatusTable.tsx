import { useState } from "react";
import {
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  deleteMedia,
  listMedia,
  processMedia,
  type MediaDto,
} from "@/api/media";
import { ClipSelectionsSection } from "@/components/ClipSelectionsSection";
import { MediaPreviewModal } from "@/components/MediaPreviewModal";
import { MediaRow } from "@/components/MediaRow";
import { StatusBadge } from "@/components/StatusBadge";

// Table re-fetches on an interval so `processing` rows flip to
// `processed`/`failed` without a manual page refresh (see
// docs/phase1-data-ingestion.md §2). Individual rows also get pushed
// updates via SSE (useMediaEvents, in MediaRow) well inside this window —
// this poll is the fallback if that connection never opens or drops.
const POLL_INTERVAL_MS = 2000;

const PROCESSABLE_STATUSES: MediaDto["status"][] = ["uploaded", "failed"];

export function StatusTable() {
  const queryClient = useQueryClient();
  const [previewMedia, setPreviewMedia] = useState<MediaDto | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

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

  const deleteMutation = useMutation({
    mutationFn: deleteMedia,
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["media"] });
      setSelectedIds((current) => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
    },
  });

  function toggleSelect(id: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds((current) =>
      current.size === media.length ? new Set() : new Set(media.map((m) => m.id)),
    );
  }

  function handleDelete(id: string) {
    if (window.confirm("Delete this media and its detected clips?")) {
      deleteMutation.mutate(id);
    }
  }

  const selectedMedia = media.filter((m) => selectedIds.has(m.id));
  const processableSelected = selectedMedia.filter((m) =>
    PROCESSABLE_STATUSES.includes(m.status),
  );

  function handleProcessSelected() {
    processableSelected.forEach((m) => processMutation.mutate(m.id));
  }

  function handleDeleteSelected() {
    if (
      window.confirm(
        `Delete ${selectedMedia.length} selected item(s) and their detected clips?`,
      )
    ) {
      selectedMedia.forEach((m) => deleteMutation.mutate(m.id));
    }
  }

  if (isLoading) {
    return <p className="text-sm text-neutral-500">Loading…</p>;
  }

  const hasRows = media.length > 0 || pendingUploads.length > 0;

  return (
    <div className="flex flex-col gap-4">
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-neutral-500">
            {selectedIds.size} selected
          </span>
          <Button
            size="sm"
            disabled={processableSelected.length === 0}
            onClick={handleProcessSelected}
          >
            Process selected
          </Button>
          <Button size="sm" variant="outline" onClick={handleDeleteSelected}>
            Delete selected
          </Button>
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox
                checked={
                  media.length > 0 && selectedIds.size === media.length
                    ? true
                    : selectedIds.size > 0
                      ? "indeterminate"
                      : false
                }
                onCheckedChange={toggleSelectAll}
                aria-label="Select all"
              />
            </TableHead>
            <TableHead>Filename</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {!hasRows && (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-neutral-400">
                No media yet — upload a video or photo above.
              </TableCell>
            </TableRow>
          )}

          {pendingUploads.map((file, i) => (
            <TableRow key={`uploading-${i}-${file.name}`}>
              <TableCell />
              <TableCell>{file.name}</TableCell>
              <TableCell>
                <StatusBadge status="uploading" stage={null} />
              </TableCell>
              <TableCell />
            </TableRow>
          ))}

          {media.map((item) => (
            <MediaRow
              key={item.id}
              media={item}
              isSelected={selectedIds.has(item.id)}
              onToggleSelect={toggleSelect}
              onView={setPreviewMedia}
              onProcess={(id) => processMutation.mutate(id)}
              onDelete={handleDelete}
              isProcessPending={
                processMutation.isPending && processMutation.variables === item.id
              }
              isDeletePending={
                deleteMutation.isPending && deleteMutation.variables === item.id
              }
            />
          ))}
        </TableBody>
      </Table>

      <ClipSelectionsSection selectedMedia={selectedMedia} />

      <MediaPreviewModal
        media={previewMedia}
        onOpenChange={(open) => !open && setPreviewMedia(null)}
      />
    </div>
  );
}
