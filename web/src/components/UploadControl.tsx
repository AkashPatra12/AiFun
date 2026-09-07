import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { UploadCloud } from "lucide-react";

import { Checkbox } from "@/components/ui/checkbox";
import { uploadMedia, type MediaKind } from "@/api/media";
import { cn } from "@/lib/utils";

const VIDEO_EXTENSIONS = ["mp4", "mov"];
const PHOTO_EXTENSIONS = ["jpg", "png"];

function kindForExtension(filename: string): MediaKind | null {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (VIDEO_EXTENSIONS.includes(ext)) return "video";
  if (PHOTO_EXTENSIONS.includes(ext)) return "photo";
  return null;
}

export function UploadControl() {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [autoProcess, setAutoProcess] = useState(true);
  const [isDragActive, setIsDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationKey: ["uploadMedia"],
    mutationFn: (file: File) => {
      const kind = kindForExtension(file.name);
      if (!kind) {
        throw new Error(
          `Unsupported file type. Accepted: ${[...VIDEO_EXTENSIONS, ...PHOTO_EXTENSIONS].join(", ")}`,
        );
      }
      return uploadMedia(file, kind, autoProcess);
    },
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["media"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  function handleFile(file: File | undefined | null) {
    if (!file) return;
    mutation.mutate(file);
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragActive(true);
        }}
        onDragLeave={() => setIsDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragActive(false);
          handleFile(e.dataTransfer.files?.[0]);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-neutral-300 p-8 text-center transition-colors hover:border-neutral-400",
          isDragActive && "border-neutral-500 bg-neutral-50",
        )}
      >
        <UploadCloud className="h-8 w-8 text-neutral-400" />
        <p className="text-sm text-neutral-600">
          Drag & drop a video or photo, or{" "}
          <span className="font-medium text-neutral-900">browse</span>
        </p>
        <p className="text-xs text-neutral-400">
          Video: .mp4 / .mov &nbsp;·&nbsp; Photo: .jpg / .png
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".mp4,.mov,.jpg,.jpeg,.png"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-neutral-700">
          <Checkbox
            checked={autoProcess}
            onCheckedChange={(checked) => setAutoProcess(checked === true)}
          />
          Start processing on upload
        </label>

        {mutation.isPending && (
          <span className="text-sm text-neutral-500">Uploading…</span>
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
