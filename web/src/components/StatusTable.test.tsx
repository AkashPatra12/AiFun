import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";

import { renderWithQueryClient } from "@/test/utils";
import { StatusTable } from "./StatusTable";
import * as mediaApi from "@/api/media";
import type { MediaDto } from "@/api/media";

vi.mock("@/api/media", async (importOriginal) => {
  const actual = await importOriginal<typeof mediaApi>();
  return {
    ...actual,
    listMedia: vi.fn(),
    processMedia: vi.fn(),
    deleteMedia: vi.fn(),
    listHighlights: vi.fn(),
  };
});

const baseMedia: MediaDto = {
  id: "1",
  kind: "video",
  status: "uploaded",
  stage: null,
  originalFilename: "a.mp4",
  mimeType: "video/mp4",
  sizeBytes: 1,
  durationSeconds: 1,
  width: 1,
  height: 1,
  thumbnailKey: null,
  createdAt: "2026-01-01T00:00:00Z",
};

function checkboxFor(filename: string) {
  return screen.getByRole("checkbox", { name: `Select ${filename}` });
}

// react-query v5's mutationFn is called with a (library-internal) second
// context argument alongside the variables — check just the id, not the
// exact call signature, so this doesn't couple to that internal shape.
function calledWithId(mockFn: { mock: { calls: unknown[][] } }, id: string) {
  return mockFn.mock.calls.some((call) => call[0] === id);
}

describe("StatusTable", () => {
  beforeEach(() => {
    vi.mocked(mediaApi.listMedia).mockReset();
    vi.mocked(mediaApi.processMedia).mockReset().mockResolvedValue(baseMedia);
    vi.mocked(mediaApi.deleteMedia).mockReset().mockResolvedValue(undefined);
    vi.mocked(mediaApi.listHighlights).mockReset().mockResolvedValue([]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("shows a Process button for an uploaded row", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, status: "uploaded" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() => expect(screen.getByText("a.mp4")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Process" })).toBeInTheDocument();
  });

  it("shows a Retry button for a failed row", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, status: "failed" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument(),
    );
  });

  it("shows View and Download for a processed row, and no action for processing", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, id: "1", status: "processed" },
      { ...baseMedia, id: "2", originalFilename: "b.mp4", status: "processing" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "Download" })).toBeInTheDocument();
    expect(screen.getByText("b.mp4")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Process" }),
    ).not.toBeInTheDocument();
  });

  it("shows an empty state with no media", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() =>
      expect(screen.getByText(/no media yet/i)).toBeInTheDocument(),
    );
  });

  it("shows the processing stage instead of a bare status", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, status: "processing", stage: "detecting_highlights" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() =>
      expect(screen.getByText("detecting highlights")).toBeInTheDocument(),
    );
  });

  it("every row has a Delete button, disabled while processing", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, id: "1", status: "processed" },
      { ...baseMedia, id: "2", originalFilename: "b.mp4", status: "processing" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() => expect(screen.getByText("b.mp4")).toBeInTheDocument());
    const deleteButtons = screen.getAllByRole("button", { name: "Delete" });
    expect(deleteButtons).toHaveLength(2);
    expect(deleteButtons[1]).toBeDisabled(); // the "processing" row
  });

  it("deletes a row after confirming", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, status: "processed" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() => expect(screen.getByText("a.mp4")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(calledWithId(vi.mocked(mediaApi.deleteMedia), "1")).toBe(true));
  });

  it("selecting rows shows a bulk action bar, and Clip selections for checked videos", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, id: "1", status: "uploaded" },
      { ...baseMedia, id: "2", originalFilename: "b.jpg", kind: "photo", status: "uploaded" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() => expect(screen.getByText("a.mp4")).toBeInTheDocument());
    expect(screen.queryByText(/selected/)).not.toBeInTheDocument();

    fireEvent.click(checkboxFor("a.mp4"));

    expect(screen.getByText("1 selected")).toBeInTheDocument();
    expect(screen.getByText("Clip selections")).toBeInTheDocument();
    expect(screen.getByText(/not processed yet/i)).toBeInTheDocument();
    // the photo is a valid bulk-select target but contributes no clip section
    fireEvent.click(checkboxFor("b.jpg"));
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    expect(screen.getAllByText(/not processed yet/i)).toHaveLength(1);
  });

  it("Process selected only processes eligible (uploaded/failed) rows", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, id: "1", status: "uploaded" },
      { ...baseMedia, id: "2", originalFilename: "b.mp4", status: "processed" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() => expect(screen.getByText("b.mp4")).toBeInTheDocument());
    fireEvent.click(checkboxFor("a.mp4"));
    fireEvent.click(checkboxFor("b.mp4"));

    fireEvent.click(screen.getByRole("button", { name: "Process selected" }));

    await waitFor(() => expect(calledWithId(vi.mocked(mediaApi.processMedia), "1")).toBe(true));
    expect(calledWithId(vi.mocked(mediaApi.processMedia), "2")).toBe(false);
  });

  it("Delete selected deletes every checked row after confirming", async () => {
    vi.mocked(mediaApi.listMedia).mockResolvedValue([
      { ...baseMedia, id: "1", status: "uploaded" },
      { ...baseMedia, id: "2", originalFilename: "b.mp4", status: "uploaded" },
    ]);
    renderWithQueryClient(<StatusTable />);

    await waitFor(() => expect(screen.getByText("b.mp4")).toBeInTheDocument());
    fireEvent.click(checkboxFor("a.mp4"));
    fireEvent.click(checkboxFor("b.mp4"));

    fireEvent.click(screen.getByRole("button", { name: "Delete selected" }));

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(calledWithId(vi.mocked(mediaApi.deleteMedia), "1")).toBe(true);
      expect(calledWithId(vi.mocked(mediaApi.deleteMedia), "2")).toBe(true);
    });
  });
});
