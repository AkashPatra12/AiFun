import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { getMediaEventsUrl, type MediaDto } from "@/api/media";

/** Subscribes to the SSE stream for one media row while `enabled`, pushing
 * each update straight into the `["media"]` list query's cache — faster
 * than waiting out StatusTable's own 2s poll, which stays running
 * regardless as a fallback if the connection drops or never opens (e.g. an
 * ad blocker, or a proxy that buffers text/event-stream responses). Also
 * invalidates the `["highlights", mediaId]` query on every message, since
 * new candidates can appear mid-job, not just once the media is done.
 */
export function useMediaEvents(mediaId: string, enabled: boolean) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled) return;

    const source = new EventSource(getMediaEventsUrl(mediaId));

    source.onmessage = (event) => {
      const updated: MediaDto = JSON.parse(event.data);
      queryClient.setQueryData<MediaDto[]>(["media"], (current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)),
      );
      queryClient.invalidateQueries({ queryKey: ["highlights", mediaId] });
    };

    source.onerror = () => {
      // The 2s GET /media poll (StatusTable) is the fallback — just stop
      // retrying a connection that isn't working rather than erroring loudly.
      source.close();
    };

    return () => source.close();
  }, [mediaId, enabled, queryClient]);
}
