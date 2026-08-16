import {observer} from "mobx-react-lite";
import {useEffect, useState} from "react";
import {Lock, Wrench} from "lucide-react";

import {useStore} from "@/hooks/use-store.jsx";
import {cn} from "@/lib/utils.js";
import {LoadingState} from "@/components/ui/loading-state.jsx";
import ToolDetail from "./tool-detail.jsx";

const ToolCard = ({tool, onClick}) => {
    return (
        <button
            onClick={onClick}
            className="rounded-card group p-6 text-left"
        >
            <div className="mb-4 flex items-center gap-3">
                <div className="card-icon-badge size-12 shrink-0">
                    {tool.source === "builtin" ? (
                        <Lock className="size-4" />
                    ) : (
                        <Wrench className="size-5" />
                    )}
                </div>
                <div className="min-w-0">
                    <div className="flex items-center gap-1">
                        <span className="truncate font-display text-xl font-medium tracking-tight">
                            {tool.name}
                        </span>
                    </div>
                    <div className="mt-0.5">
                        <span
                            className={cn(
                                "rounded-sm px-1.5 py-0.5 text-[9px]",
                                tool.source === "user"
                                    ? "bg-foreground/10 text-foreground/80"
                                    : "bg-muted/20 text-muted-foreground"
                            )}
                        >
                            {tool.source}
                        </span>
                    </div>
                </div>
            </div>
            <p className="line-clamp-2 text-[11px] text-muted-foreground/70">
                {tool.description || "(no description)"}
            </p>
        </button>
    );
}

const SectionTitle = ({children}) => {
    return (
        <div className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
            {children}
        </div>
    );
}

const ToolsView = observer(() => {
    const {toolStore} = useStore();
    const [selected, setSelected] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        toolStore.loadTools().finally(() => setLoading(false));
    }, [toolStore]);

    if (selected) {
        return <ToolDetail name={selected} onBack={() => setSelected(null)} />;
    }

    if (loading) return <LoadingState>Loading tools…</LoadingState>;

    const builtin = toolStore.tools.filter((t) => t.source === "builtin");
    const user = toolStore.tools.filter((t) => t.source === "user");

    return (
        <div className="h-full overflow-y-auto">
            <div className="mx-auto max-w-5xl px-6 py-8">
                <div className="mb-6 flex items-center gap-2.5">
                    <span className="flex size-8 items-center justify-center rounded-lg bg-foreground/5 ring-1 ring-border/60">
                        <Wrench className="size-4 text-foreground/70" />
                    </span>
                    <h1 className="h-display">Tools</h1>
                    <span className="text-sm text-muted-foreground">
                        ({toolStore.tools.length})
                    </span>
                </div>

                {builtin.length > 0 && (
                    <>
                        <SectionTitle>Built-in</SectionTitle>
                        <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {builtin.map((t) => (
                                <ToolCard
                                    key={t.name}
                                    tool={t}
                                    onClick={() => setSelected(t.name)}
                                />
                            ))}
                        </div>
                    </>
                )}

                {user.length > 0 && (
                    <>
                        <SectionTitle>Custom</SectionTitle>
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {user.map((t) => (
                                <ToolCard
                                    key={t.name}
                                    tool={t}
                                    onClick={() => setSelected(t.name)}
                                />
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
});

export default ToolsView;
