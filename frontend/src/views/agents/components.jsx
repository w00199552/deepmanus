import {AlertCircle, Check} from "lucide-react";

import {cn} from "@/lib/utils.js";

// ─── shared small components (used by agents-view / agent-detail / create-agent) ──

export function Centered({children}) {
    return (
        <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">{children}</p>
        </div>
    );
}

export function TabBtn({active, onClick, icon, children}) {
    return (
        <button
            onClick={onClick}
            className={cn(
                "flex items-center gap-1.5 rounded-lg px-3 py-2 text-[13px] transition",
                active
                    ? "bg-foreground/8 text-foreground font-medium"
                    : "text-muted-foreground hover:bg-foreground/6 hover:text-foreground"
            )}
        >
            {icon}
            {children}
        </button>
    );
}

export function Toast({type, message}) {
    return (
        <div
            className={cn(
                "fixed right-4 top-14 z-50 flex items-center gap-2 rounded-full px-4 py-2.5 text-[13px] shadow-lg anim-rise",
                type === "error"
                    ? "bg-destructive/15 text-destructive"
                    : "bg-accent/15 text-accent accent-glow"
            )}
        >
            {type === "error" ? (
                <AlertCircle className="size-3.5"/>
            ) : (
                <Check className="size-3.5"/>
            )}
            {message}
        </div>
    );
}
