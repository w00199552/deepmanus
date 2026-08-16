import {observer} from "mobx-react-lite";
import {useEffect, useState} from "react";
import {AlertCircle, Bot, Check, ChevronLeft, FileText, Save, Sparkles, Wrench,} from "lucide-react";
import {toast} from "sonner";
import MDEditor from "@uiw/react-md-editor";

import {useStore} from "@/hooks/use-store.jsx";
import {useTheme} from "@/hooks/use-theme.js";
import {cn} from "@/lib/utils.js";
import {Tabs, TabsList, TabsTrigger} from "@/components/ui/tabs.jsx";

// vertical shadcn Tabs trigger — left-aligned, fills width, matches sidebar style
const tabTriggerCls =
    "w-full justify-start gap-1.5 rounded-lg px-3 py-2 text-[13px] font-normal data-[state=active]:bg-foreground/8 data-[state=active]:font-medium data-[state=active]:text-foreground data-[state=active]:shadow-none hover:bg-foreground/6 hover:text-foreground";

// ─── Create new agent form ──────────────────────────────────────────────────
const CreateAgent = observer(({onBack, onCreated}) => {

    const {agentStore: s} = useStore();
    const {isDark} = useTheme();
    const colorMode = isDark ? "dark" : "light";
    const [tab, setTab] = useState("info");
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [prompt, setPrompt] = useState("");
    const [creating, setCreating] = useState(false);
    const [selectedTools, setSelectedTools] = useState(new Set());
    const [selectedSkills, setSelectedSkills] = useState(new Set());

    useEffect(() => {
        s.loadTools();
        s.loadSkills();
    }, [s]);

    const toggleTool = (toolName) => {
        setSelectedTools((prev) => {
            const next = new Set(prev);
            if (next.has(toolName)) next.delete(toolName);
            else next.add(toolName);
            return next;
        });
    };

    const toggleSkillItem = (skillName) => {
        setSelectedSkills((prev) => {
            const next = new Set(prev);
            if (next.has(skillName)) next.delete(skillName);
            else next.add(skillName);
            return next;
        });
    };

    const handleCreate = async () => {
        if (!name.trim() || creating) return;
        setCreating(true);
        const ok = await s.create(
            name.trim(),
            prompt,
            [...selectedTools],
            [...selectedSkills],
            description
        );
        setCreating(false);
        if (ok) {
            toast.success(`Agent "${name.trim()}" created`);
            onCreated(name.trim());
        }
    };

    return (
        <div className="flex h-full">
            {/* left sidebar: tabs */}
            <div className="flex w-56 shrink-0 flex-col border-r border-border/60 bg-sidebar/20">
                <button
                    onClick={onBack}
                    className="flex items-center gap-1 px-4 py-3 text-sm text-muted-foreground transition hover:bg-foreground/5 hover:text-foreground"
                >
                    <ChevronLeft className="size-4"/>
                    Agents
                </button>
                <div className="px-4 py-2">
                    <div className="text-sm font-medium text-muted-foreground">
                        New Agent
                    </div>
                </div>
                <div className="mt-2 px-2">
                    <Tabs
                        value={tab}
                        onValueChange={setTab}
                        orientation="vertical"
                        className="gap-0.5"
                    >
                        <TabsList
                            className="flex h-auto w-full flex-col items-stretch gap-0.5 rounded-none bg-transparent p-0">
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
                        onClick={handleCreate}
                        disabled={!name.trim() || creating}
                        className="flex w-full items-center justify-center gap-1.5 rounded-full bg-accent/15 px-3 py-2 text-[13px] text-accent transition hover:bg-accent/25 disabled:opacity-50"
                    >
                        <Save className="size-3.5"/>
                        {creating ? "Creating…" : "Create"}
                    </button>
                </div>
            </div>

            {/* right content */}
            <div className="min-h-0 flex-1 overflow-hidden">
                <div className="flex h-full w-full flex-col px-8 py-8">
                    {tab === "info" && (
                        <div className="space-y-4">
                            <h2 className="text-sm font-medium">Agent Info</h2>
                            <div>
                                <label className="mb-1 block text-[12px] font-medium text-muted-foreground">
                                    Name
                                </label>
                                <input
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    placeholder="e.g. code_reviewer"
                                    className="w-full rounded-lg border border-border/60 bg-sidebar/30 px-3 py-2 text-[13px] outline-none focus:border-accent/40"
                                />
                                <p className="mt-1 text-[11px] text-muted-foreground/60">
                                    Unique agent identifier. Cannot be changed
                                    after creation.
                                </p>
                            </div>
                            <div>
                                <label className="mb-1 block text-[12px] font-medium text-muted-foreground">
                                    Description
                                </label>
                                <textarea
                                    value={description}
                                    onChange={(e) =>
                                        setDescription(e.target.value)
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
                                    value={prompt}
                                    onChange={(val) => setPrompt(val || "")}
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
                            <h2 className="mb-3 text-sm font-medium">Tools</h2>
                            <p className="mb-4 text-[12px] text-muted-foreground">
                                Select tools for this agent. Create or import
                                new tools in the Tools page.
                            </p>
                            <div className="space-y-2">
                                {s.tools.map((tool) => {
                                    const checked = selectedTools.has(
                                        tool.name
                                    );
                                    return (
                                        <button
                                            key={tool.name}
                                            onClick={() =>
                                                toggleTool(tool.name)
                                            }
                                            className={cn(
                                                "flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition",
                                                checked
                                                    ? "border-accent/30 bg-accent/5"
                                                    : "border-border/40 hover:border-border/80"
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
                                Select skills for this agent.
                            </p>
                            {s.skills.length === 0 ? (
                                <p className="text-[12px] text-muted-foreground/60">
                                    No skills installed in ~/.openmanus/skills/.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {s.skills.map((skill) => {
                                        const checked = selectedSkills.has(
                                            skill.name
                                        );
                                        return (
                                            <button
                                                key={skill.name}
                                                onClick={() =>
                                                    toggleSkillItem(skill.name)
                                                }
                                                className={cn(
                                                    "flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition",
                                                    checked
                                                        ? "border-accent/30 bg-accent/5"
                                                        : "border-border/40 hover:border-border/80"
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
                                                    <span className="text-[13px] font-medium">
                                                        {skill.name}
                                                    </span>
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

export default CreateAgent;
