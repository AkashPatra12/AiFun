import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useMediaEvents } from "./useMediaEvents";
import type { MediaDto } from "@/api/media";

class TrackedEventSource {
  static instances: TrackedEventSource[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;
  constructor(public url: string) {
    TrackedEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

const baseMedia: MediaDto = {
  id: "1",
  kind: "video",
  status: "processing",
  stage: "transcribing",
  originalFilename: "a.mp4",
  mimeType: "video/mp4",
  sizeBytes: 1,
  durationSeconds: 1,
  width: 1,
  height: 1,
  thumbnailKey: null,
  createdAt: "2026-01-01T00:00:00Z",
};

function wrapper(queryClient: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useMediaEvents", () => {
  beforeEach(() => {
    TrackedEventSource.instances = [];
    vi.stubGlobal("EventSource", TrackedEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not open a connection when disabled", () => {
    const queryClient = new QueryClient();
    renderHook(() => useMediaEvents("1", false), { wrapper: wrapper(queryClient) });

    expect(TrackedEventSource.instances).toHaveLength(0);
  });

  it("opens a connection to the media's events URL when enabled", () => {
    const queryClient = new QueryClient();
    renderHook(() => useMediaEvents("1", true), { wrapper: wrapper(queryClient) });

    expect(TrackedEventSource.instances).toHaveLength(1);
    expect(TrackedEventSource.instances[0].url).toContain("/media/1/events");
  });

  it("patches the matching row in the media list cache on message", () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(["media"], [baseMedia, { ...baseMedia, id: "2" }]);
    renderHook(() => useMediaEvents("1", true), { wrapper: wrapper(queryClient) });

    const updated = { ...baseMedia, status: "processed", stage: null };
    TrackedEventSource.instances[0].emit(updated);

    const cached = queryClient.getQueryData<MediaDto[]>(["media"]);
    expect(cached?.find((m) => m.id === "1")).toEqual(updated);
    expect(cached?.find((m) => m.id === "2")?.status).toBe("processing"); // untouched
  });

  it("invalidates the highlights query on each message", () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    renderHook(() => useMediaEvents("1", true), { wrapper: wrapper(queryClient) });

    TrackedEventSource.instances[0].emit(baseMedia);

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["highlights", "1"] });
  });

  it("closes the connection on unmount", () => {
    const queryClient = new QueryClient();
    const { unmount } = renderHook(() => useMediaEvents("1", true), {
      wrapper: wrapper(queryClient),
    });

    unmount();

    expect(TrackedEventSource.instances[0].closed).toBe(true);
  });
});
