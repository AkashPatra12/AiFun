import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import { renderWithQueryClient } from "@/test/utils";
import { HighlightsPanel } from "./HighlightsPanel";
import * as mediaApi from "@/api/media";
import type { HighlightDto } from "@/api/media";

vi.mock("@/api/media", async (importOriginal) => {
  const actual = await importOriginal<typeof mediaApi>();
  return { ...actual, listHighlights: vi.fn() };
});

const baseHighlight: HighlightDto = {
  id: "h1",
  mediaId: "1",
  startSeconds: 0,
  endSeconds: 12,
  score: 0.87,
  reason: "motion=0.90, face detected",
  status: "rendered",
  clipKey: "/data/output/highlights/h1.mp4",
  createdAt: "2026-01-01T00:00:00Z",
};

describe("HighlightsPanel", () => {
  beforeEach(() => {
    vi.mocked(mediaApi.listHighlights).mockReset();
  });

  it("shows a detecting message before any highlights exist", async () => {
    vi.mocked(mediaApi.listHighlights).mockResolvedValue([]);
    renderWithQueryClient(<HighlightsPanel mediaId="1" />);

    await waitFor(() =>
      expect(screen.getByText(/detecting highlights/i)).toBeInTheDocument(),
    );
  });

  it("lists a rendered highlight's timestamp, score, reason, and preview", async () => {
    vi.mocked(mediaApi.listHighlights).mockResolvedValue([baseHighlight]);
    renderWithQueryClient(<HighlightsPanel mediaId="1" />);

    await waitFor(() => expect(screen.getByText("0:00–0:12")).toBeInTheDocument());
    expect(screen.getByText(/score 0.87/)).toBeInTheDocument();
    expect(screen.getByText(/face detected/)).toBeInTheDocument();
    expect(document.querySelector("video")?.getAttribute("src")).toContain(
      "/highlights/h1/preview",
    );
  });

  it("shows the status text instead of a preview while still rendering", async () => {
    vi.mocked(mediaApi.listHighlights).mockResolvedValue([
      { ...baseHighlight, status: "pending", clipKey: null },
    ]);
    renderWithQueryClient(<HighlightsPanel mediaId="1" />);

    await waitFor(() => expect(screen.getByText("pending")).toBeInTheDocument());
    expect(document.querySelector("video")).not.toBeInTheDocument();
  });
});
