import {observer} from "mobx-react-lite";
import {useState} from "react";
import {AlertCircle, Bot, Check, ChevronLeft, FileText, Image, Save, Sparkles, Wrench,} from "lucide-react";
import {toast} from "sonner";
import MDEditor from "@uiw/react-md-editor";

import {useStore} from "@/hooks/use-store.jsx";
import {useTheme} from "@/hooks/use-theme.js";
import {Avatar} from "@/components/avatar.jsx";
import {AvatarPickerDialog} from "@/components/avatar-picker.jsx";
import {cn} from "@/lib/utils.js";
import {Tabs, TabsList, TabsTrigger} from "@/components/ui/tabs.jsx";
import {LoadingState} from "@/components/ui/loading-state.jsx";

// vertical shadcn Tabs trigger — left-aligned, fills width, matches sidebar style
const tabTriggerCls =
    "w-full justify-start gap-1.5 rounded-lg px-3 py-2 text-[13px] font-normal data-[state=active]:bg-foreground/8 data-[state=active]:font-medium data-[state=active]:text-foreground data-[state=active]:shadow-none hover:bg-foreground/6 hover:text-foreground";

// ─── Agent detail (left tabs + right content) ───────────────────────────────
const AgentDetail = observer(({name, onBack}) => {

    const {agentStore: s} = useStore();
    const {isDark} = useTheme();
    const colorMode = isDark ? "dark" : "light";
    const [tab, setTab] = useState("prompt");
    const [avatarPickerOpen, setAvatarPickerOpen] = useState(false);
    const [saving, setSaving] = useState(false);

    const handleSave = async () => {
        setSaving(true);
        const ok = await s.save();
        if (ok) toast.success("Agent saved successfully");
        setSaving(false);
    };

    if (!s.current) return <LoadingState>Loading…</LoadingState>;

    return (
        <div className="flex h-full">
            <div className="flex w-56 shrink-0 flex-col border-r border-border/60 bg-sidebar/20">
                <button
                    onClick={onBack}
                    className="flex items-center gap-1 px-4 py-3 text-sm text-muted-foreground transition hover:bg-foreground/5 hover:text-foreground"
                >
                    <ChevronLeft className="size-4"/>
                    Agents
                </button>

                <div className="px-4 py-2">
                    <div className="flex items-center gap-2">
                        <Avatar seed={s.current.name} size={36}/>
                        <div>
                            <div className="text-sm font-medium">
                                {s.current.name}
                            </div>
                            <code className="text-[10px] text-muted-foreground">
                                {s.current.name}
                            </code>
                        </div>
                    </div>
                </div>

                <div className="mt-2 px-2">
                    <Tabs
                        value={tab}
                        onValueChange={setTab}
                        orientation="vertical"
                        className="gap-0.5"
                    >
                        <TabsList className="flex h-auto w-full flex-col items-stretch gap-0.5 rounded-none bg-transparent p-0">
                            <TabsTrigger value="info" className={tabTriggerCls}>
                                <Bot className="size-3.5"/>
                                Info
                            </TabsTrigger>
                            <TabsTrigger value="prompt" className={tabTriggerCls}>
                                <FileText className="size-3.5"/>
                                Prompt
                            </TabsTrigger>
                            <TabsTrigger value="tools" className={tabTriggerCls}>
                                <Wrench className="size-3.5"/>
                                Tools
                            </TabsTrigger>
                            <TabsTrigger value="skills" className={tabTriggerCls}>
                                <Sparkles className="size-3.5"/>
                                Skills
                            </TabsTrigger>
                            <TabsTrigger value="subagents" className={tabTriggerCls}>
                                <Bot className="size-3.5"/>
                                SubAgents
                            </TabsTrigger>
                            <TabsTrigger value="interrupt" className={tabTriggerCls}>
                                <AlertCircle className="size-3.5"/>
                                Interrupt
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                </div>

                <div className="mt-auto p-3">
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="flex w-full items-center justify-center gap-1.5 rounded-full bg-accent/15 px-3 py-2 text-[13px] text-accent transition hover:bg-accent/25 disabled:opacity-50"
                    >
                        <Save className="size-3.5"/>
                        {saving ? "Saving…" : "Save"}
                    </button>
                </div>
            </div>

            {/* right content */}
            <div className="min-h-0 flex-1 overflow-hidden">
                <div className="flex h-full w-full flex-col px-8 py-8">
                    {tab === "info" && (
                        <div className="space-y-4">
                            {/* Avatar */}
                            <div className="flex items-center gap-4">
                                <Avatar
                                    seed={s.current.name}
                                    size={64}
                                />
                                <button
                                    onClick={() => setAvatarPickerOpen(true)}
                                    className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-sidebar/30 px-3 py-2 text-[12px] text-muted-foreground transition hover:border-accent/40 hover:text-foreground"
                                >
                                    <Image className="size-3.5"/>
                                    选择头像
                                </button>
                            </div>
                            <AvatarPickerDialog
                                open={avatarPickerOpen}
                                onOpenChange={setAvatarPickerOpen}
                            />
                            <div>
                                <label className="mb-1 block text-[12px] font-medium text-muted-foreground">
                                    Name
                                </label>
                                <div
                                    className="rounded-lg border border-border/40 bg-sidebar/20 px-3 py-2 text-[13px] text-muted-foreground">
                                    {s.current.name}
                                </div>
                            </div>
                            <div>
                                <label className="mb-1 block text-[12px] font-medium text-muted-foreground">
                                    Description
                                </label>
                                <textarea
                                    value={s.descriptionDraft}
                                    onChange={(e) =>
                                        s.setDescriptionDraft(e.target.value)
                                    }
                                    placeholder="Describe what this agent does and when to use it..."
                                    className="min-h-[80px] w-full resize-y rounded-lg border border-border/60 bg-sidebar/30 px-3 py-2 text-[13px] outline-none focus:border-accent/40"
                                />
                                <p className="mt-1 text-[11px] text-muted-foreground/60">
                                    Used by Manus/TeamLeader to decide when to
                                    dispatch to this agent.
                                </p>
                            </div>
                        </div>
                    )}

                    {tab === "prompt" && (
                        <div className="flex h-full flex-col">
                            <h2 className="mb-3 shrink-0 text-sm font-medium">
                                System Prompt
                            </h2>
                            <div className="min-h-0 flex-1">
                                <MDEditor
                                    value={s.promptDraft}
                                    onChange={(val) =>
                                        s.setPromptDraft(val || "")
                                    }
                                    height="100%"
                                    preview="live"
                                    data-color-mode={colorMode}
                                    style={{height: "100%"}}
                                />
                            </div>
                        </div>
                    )}

                    {tab === "tools" && (
                        <div>
                            <h2 className="mb-3 text-sm font-medium">
                                Tools Configuration
                            </h2>
                            <p className="mb-4 text-[12px] text-muted-foreground">
                                Select which tools this agent can use.
                            </p>
                            <div className="space-y-2">
                                {s.tools.map((tool) => {
                                    const checked = s.toolDraft.has(tool.name);
                                    return (
                                        <button
                                            key={tool.name}
                                            onClick={() => s.toggleTool(tool.name)}
                                            className={cn(
                                                "flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition hover:border-border/80",
                                                checked
                                                    ? "border-accent/30 bg-accent/5"
                                                    : "border-border/40"
                                            )}
                                        >
                                            <div
                                                className={cn(
                                                    "flex size-5 shrink-0 items-center justify-center rounded border",
                                                    checked
                                                        ? "border-accent bg-accent"
                                                        : "border-border/60"
                                                )}
                                            >
                                                {checked && (
                                                    <Check className="size-3 text-accent-foreground"/>
                                                )}
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-[13px] font-medium">
                                                        {tool.name}
                                                    </span>
                                                    <span
                                                        className={cn(
                                                            "rounded-sm px-1 py-0.5 text-[9px]",
                                                            tool.source ===
                                                            "user"
                                                                ? "bg-foreground/10 text-foreground/80"
                                                                : "bg-muted/20 text-muted-foreground"
                                                        )}
                                                    >
                                                        {tool.source}
                                                    </span>
                                                </div>
                                                <p className="truncate text-[11px] text-muted-foreground">
                                                    {tool.description}
                                                </p>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {tab === "skills" && (
                        <div>
                            <h2 className="mb-3 text-sm font-medium">Skills</h2>
                            <p className="mb-4 text-[12px] text-muted-foreground">
                                Skills are loaded progressively by the agent
                                (SKILL.md + scripts). Select which skills this
                                agent can access.
                            </p>
                            {s.skills.length === 0 ? (
                                <p className="text-[12px] text-muted-foreground/60">
                                    No skills installed. Create skills in
                                    ~/.openmanus/skills/.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {s.skills.map((skill) => {
                                        const checked = s.skillDraft.has(
                                            skill.name
                                        );
                                        return (
                                            <button
                                                key={skill.name}
                                                onClick={() => s.toggleSkill(skill.name)}
                                                className={cn(
                                                    "flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition hover:border-border/80",
                                                    checked
                                                        ? "border-accent/30 bg-accent/5"
                                                        : "border-border/40"
                                                )}
                                            >
                                                <div
                                                    className={cn(
                                                        "flex size-5 shrink-0 items-center justify-center rounded border",
                                                        checked
                                                            ? "border-accent bg-accent"
                                                            : "border-border/60"
                                                    )}
                                                >
                                                    {checked && (
                                                        <Check className="size-3 text-accent-foreground"/>
                                                    )}
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-1.5">
                                                        <span className="text-[13px] font-medium">
                                                            {skill.name}
                                                        </span>
                                                        {skill.has_scripts && (
                                                            <span
                                                                className="rounded-sm bg-foreground/10 px-1 py-0.5 text-[9px] text-muted-foreground">
                                                                scripts
                                                            </span>
                                                        )}
                                                    </div>
                                                    <p className="truncate text-[11px] text-muted-foreground">
                                                        {skill.description}
                                                    </p>
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {tab === "subagents" && (
                        <div>
                            <h2 className="mb-3 text-sm font-medium">
                                SubAgents
                            </h2>
                            <p className="text-[12px] text-muted-foreground">
                                Configure which agents this agent can dispatch
                                to. Coming soon.
                            </p>
                        </div>
                    )}

                    {tab === "interrupt" && (
                        <div>
                            <h2 className="mb-3 text-sm font-medium">
                                Human-in-the-Loop
                            </h2>
                            <p className="text-[12px] text-muted-foreground">
                                Configure which tools require human approval
                                before execution. Coming soon.
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
});

export default AgentDetail;
