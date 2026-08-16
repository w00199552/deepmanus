import runtimeService from "@/services/runtime-service.js";

export class StreamClient {
    subscribe(opts, cb) {
        const url = runtimeService.getStreamUrl(opts);
        const es = new EventSource(url);
        es.onmessage = (ev) => {
            if (ev.data === "[DONE]") {
                if (import.meta.env.DEV) console.log("[SSE] [DONE]");
                cb.onDone?.();
                return;
            }
            try {
                const evt = JSON.parse(ev.data);
                cb.onEvent?.(evt);
            } catch {
                /* ignore malformed frames */
            }
        };
        es.onerror = (e) => {
            // EventSource auto-reconnects by default after the server closes a run's
            // response; that reconnect is EXPECTED (it's how we wait for the next
            // run). Only surface genuinely unexpected errors.
            cb.onError?.(e);
        };
        return {
            dispose() {
                es.close();
            },
        };
    }
}
