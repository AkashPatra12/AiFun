import { describe, it, expect, vi, beforeEach } from "vitest";

import { uploadMedia, listMedia, getMediaOutputUrl } from "./media";

function mockFetchOnce(body: unknown, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      statusText: "status",
      json: async () => body,
    } as Response),
  );
}

describe("media api client", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("uploadMedia POSTs a multipart form with the file, kind, and autoProcess", async () => {
    mockFetchOnce({ id: "1", status: "uploaded" });
    const file = new File(["data"], "clip.mp4", { type: "video/mp4" });

    const result = await uploadMedia(file, "video", true);

    expect(result).toEqual({ id: "1", status: "uploaded" });
    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/media");
    expect(options?.method).toBe("POST");
    const body = options?.body as FormData;
    expect(body.get("file")).toBe(file);
    expect(body.get("kind")).toBe("video");
    expect(body.get("autoProcess")).toBe("true");
  });

  it("throws the server's detail message on a non-ok response", async () => {
    mockFetchOnce({ detail: "bad kind" }, false, 400);

    await expect(listMedia()).rejects.toThrow("bad kind");
  });

  it("getMediaOutputUrl builds the output URL for a media id", () => {
    expect(getMediaOutputUrl("abc-123")).toMatch(/\/media\/abc-123\/output$/);
  });
});
