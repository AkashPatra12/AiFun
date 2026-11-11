import { vi } from "vitest";

import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement EventSource — an inert stub so components using
// it (MediaRow, via useMediaEvents) don't crash tests that never assert on
// SSE behavior themselves. useMediaEvents.test.ts installs its own richer
// mock (tracking messages/close) for the tests that actually need one.
class InertEventSource {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  constructor(public url: string) {}
  close() {}
}
vi.stubGlobal("EventSource", InertEventSource);
