import { Loader2 } from "lucide-react";

import type { MediaDto } from "@/api/media";

const STAGE_LABELS: Record<string, string> = {
  transcribing: "transcribing",
  detecting_highlights: "detecting highlights",
  rendering_previews: "rendering previews",
  exporting: "exporting",
};

const STYLES: Record<string, string> = {
  uploading: "bg-neutral-100 text-neutral-600",
  uploaded: "bg-blue-50 text-blue-700",
  processing: "bg-amber-50 text-amber-700",
  processed: "bg-green-50 text-green-700",
  failed: "bg-red-50 text-red-700",
};

export function StatusBadge({
  status,
  stage,
}: {
  status: MediaDto["status"] | "uploading";
  stage: string | null;
}) {
  const label =
    status === "processing" && stage ? (STAGE_LABELS[stage] ?? stage) : status;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      {(status === "uploading" || status === "processing") && (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      {label}
    </span>
  );
}
