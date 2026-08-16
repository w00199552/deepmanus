import {observer} from "mobx-react-lite";
import {useEffect, useState} from "react";
import {Check} from "lucide-react";
import {toast} from "sonner";

import {useStore} from "@/hooks/use-store.jsx";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog.jsx";
import {cn} from "@/lib/utils.js";

/**
 * AvatarPickerDialog — pick one of the bundled avatar presets (offline).
 *
 * Loads the preset list lazily from the backend on first open, renders a
 * scrollable grid, highlights the agent's current selection, and applies
 * the chosen preset via agentStore.setAvatar(id). Closes on success.
 *
 * @param {boolean} open
 * @param {(open:boolean)=>void} onOpenChange
 */
export const AvatarPickerDialog = observer(function AvatarPickerDialog({
    open,
    onOpenChange,
}) {
    const {agentStore: s} = useStore();
    const [pending, setPending] = useState(null); // presetId being applied

    // Lazy-load presets the first time the dialog opens.
    useEffect(() => {
        if (open && !s.presetListLoaded) s.loadAvatarPresets();
    }, [open, s]);

    const currentAvatar = s.current?.avatar || "";

    async function apply(presetId) {
        if (pending) return;
        setPending(presetId);
        try {
            const ok = await s.setAvatar(presetId);
            if (ok) {
                toast.success("头像已更新");
                onOpenChange(false);
            }
        } finally {
            setPending(null);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>选择头像</DialogTitle>
                    <DialogDescription>
                        从内置头像库中选择一张，完全离线（共 {s.presetList.length} 张）。
                    </DialogDescription>
                </DialogHeader>

                <div className="max-h-[60vh] overflow-y-auto pr-1">
                    {s.presetList.length === 0 ? (
                        <div className="py-8 text-center text-[13px] text-muted-foreground">
                            {s.presetListLoaded ? "暂无可用头像" : "加载中…"}
                        </div>
                    ) : (
                        <div className="grid grid-cols-6 gap-2 sm:grid-cols-8">
                            {s.presetList.map((p) => {
                                const active = p.id === currentAvatar;
                                const busy = pending === p.id;
                                return (
                                    <button
                                        key={p.id}
                                        onClick={() => apply(p.id)}
                                        disabled={!!pending}
                                        title={p.id}
                                        className={cn(
                                            "relative aspect-square overflow-hidden rounded-lg ring-1 transition",
                                            "hover:ring-accent/60 hover:bg-accent/5",
                                            active
                                                ? "ring-2 ring-accent bg-accent/10"
                                                : "ring-border/50 bg-sidebar/30",
                                            pending && !busy && "opacity-40"
                                        )}
                                    >
                                        <img
                                            src={p.url}
                                            alt={`avatar ${p.id}`}
                                            className="size-full object-cover"
                                            loading="lazy"
                                        />
                                        {active && (
                                            <span className="absolute bottom-0.5 right-0.5 flex size-4 items-center justify-center rounded-full bg-accent text-white">
                                                <Check className="size-2.5"/>
                                            </span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
});
