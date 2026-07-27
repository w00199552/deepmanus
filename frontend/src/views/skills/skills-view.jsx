import {observer} from "mobx-react-lite";
import {useEffect, useState} from "react";
import {Sparkles} from "lucide-react";

import {useStore} from "@/hooks/use-store.jsx";
import {SkillDetail} from "./skill-detail.jsx";

export const SkillsView = observer(function SkillsView() {
    const {skillStore} = useStore();
    const [selected, setSelected] = useState(null);

    useEffect(() => {
        skillStore.loadSkills();
    }, [skillStore]);

    if (selected) {
        return <SkillDetail name={selected} onBack={() => setSelected(null)} />;
    }

    if (skillStore.loading) return <Centered>Loading skills…</Centered>;

    return (
        <div className="h-full overflow-y-auto">
            <div className="mx-auto max-w-5xl px-6 py-8">
                <div className="mb-6 flex items-center gap-2.5">
                    <span className="flex size-8 items-center justify-center rounded-lg bg-foreground/5 ring-1 ring-border/60">
                        <Sparkles className="size-4 text-foreground/70" />
                    </span>
                    <h1 className="h-display">Skills</h1>
                    <span className="text-sm text-muted-foreground">
                        ({skillStore.skills.length})
                    </span>
                </div>

                {skillStore.skills.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-border/40 p-12 text-center">
                        <Sparkles className="mx-auto mb-3 size-8 text-muted-foreground/30" />
                        <p className="text-sm text-muted-foreground">
                            No skills installed.
                        </p>
                        <p className="mt-1 text-[12px] text-muted-foreground/60">
                            Copy skill directories to ~/.openmanus/skills/
                        </p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {skillStore.skills.map((s) => (
                            <SkillCard
                                key={s.name}
                                skill={s}
                                onClick={() => setSelected(s.name)}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
});

function SkillCard({skill, onClick}) {
    return (
        <button
            onClick={onClick}
            className="rounded-card group p-6 text-left"
        >
            <div className="mb-4 flex items-center gap-3">
                <div className="card-icon-badge size-12 shrink-0">
                    <Sparkles className="size-5" />
                </div>
                <div className="min-w-0">
                    <span className="truncate font-display text-xl font-medium tracking-tight">
                        {skill.name}
                    </span>
                    <div className="mt-0.5 flex gap-1">
                        {skill.has_scripts && (
                            <span className="rounded-sm bg-foreground/10 px-1.5 py-0.5 text-[9px] text-muted-foreground">
                                scripts
                            </span>
                        )}
                        {skill.has_references && (
                            <span className="rounded-sm bg-foreground/8 px-1.5 py-0.5 text-[9px] text-muted-foreground">
                                refs
                            </span>
                        )}
                    </div>
                </div>
            </div>
            <p className="line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
                {skill.description || "(no description)"}
            </p>
        </button>
    );
}

function Centered({children}) {
    return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {children}
        </div>
    );
}
