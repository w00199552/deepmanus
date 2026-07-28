import {cn} from "@/lib/utils";
import {Spinner} from "@/components/ui/spinner.jsx";

/**
 * LoadingState — full-size centered "spinner + message" placeholder.
 *
 * Used for loading / pending states across views (agent/skill/tool lists &
 * details). Replaces the per-view `Centered` duplicates with a single
 * semantic component, and normalizes on a Spinner (some call sites previously
 * showed bare "Loading…" text with no spinner).
 *
 * @param {string} [children] — optional message; defaults to "Loading…"
 */
export function LoadingState({children = "Loading…", className}) {
    return (
        <div
            className={cn(
                "flex h-full items-center justify-center gap-2 text-sm text-muted-foreground",
                className
            )}
        >
            <Spinner/>
            {children}
        </div>
    );
}
