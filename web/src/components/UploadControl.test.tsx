import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";

import { renderWithQueryClient } from "@/test/utils";
import { UploadControl } from "./UploadControl";
import * as mediaApi from "@/api/media";
import type { MediaDto } from "@/api/media";

vi.mock("@/api/media", async (importOriginal) => {
  const actual = await importOriginal<typeof mediaApi>();
  return { ...actual, uploadMedia: vi.fn() };
});

const uploadedMedia: MediaDto = {
  id: "1",
  kind: "video",
  status: "uploaded",
  stage: null,
  originalFilename: "clip.mp4",
  mimeType: "video/mp4",
  sizeBytes: 1,
  durationSeconds: null,
  width: null,
  height: null,
  thumbnailKey: null,
  createdAt: "2026-01-01T00:00:00Z",
};

function getFileInput() {
  return document.querySelector('input[type="file"]') as HTMLInputElement;
}

describe("UploadControl", () => {
  beforeEach(() => {
    vi.mocked(mediaApi.uploadMedia).mockReset();
  });

  it("uploads a selected file with kind inferred from its extension", async () => {
    vi.mocked(mediaApi.uploadMedia).mockResolvedValue(uploadedMedia);
    renderWithQueryClient(<UploadControl />);

    const file = new File(["data"], "clip.mp4", { type: "video/mp4" });
    fireEvent.change(getFileInput(), { target: { files: [file] } });

    await waitFor(() =>
      expect(mediaApi.uploadMedia).toHaveBeenCalledWith(file, "video", true),
    );
  });

  it("rejects an unsupported file type without calling the API", async () => {
    renderWithQueryClient(<UploadControl />);

    const file = new File(["data"], "clip.avi", { type: "video/x-msvideo" });
    fireEvent.change(getFileInput(), { target: { files: [file] } });

    await waitFor(() =>
      expect(screen.getByText(/unsupported file type/i)).toBeInTheDocument(),
    );
    expect(mediaApi.uploadMedia).not.toHaveBeenCalled();
  });

  it("unchecking 'start processing on upload' is reflected in the next upload", async () => {
    vi.mocked(mediaApi.uploadMedia).mockResolvedValue(uploadedMedia);
    renderWithQueryClient(<UploadControl />);

    fireEvent.click(screen.getByRole("checkbox"));

    const file = new File(["data"], "clip.mp4", { type: "video/mp4" });
    fireEvent.change(getFileInput(), { target: { files: [file] } });

    await waitFor(() =>
      expect(mediaApi.uploadMedia).toHaveBeenCalledWith(file, "video", false),
    );
  });
});
