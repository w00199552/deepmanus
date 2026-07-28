import {observer} from "mobx-react-lite";
import {useEffect, useState} from "react";
import {Bot, Lock, Wrench} from "lucide-react";

import {useStore} from "@/hooks/use-store.jsx";
import {Avatar} from "@/components/avatar.jsx";
import {FancyButton} from "@/components/ui/fancy-button.jsx";
import AgentDetail from "./agent-detail.jsx";
import CreateAgent from "./create-agent.jsx";
import {Centered, Toast} from "./components.jsx";

/**
 * AgentsView — card grid → click to open config (left tabs: Prompt / Tools).
 * Calls agentStore actions only (view → store → service).
 */
const AgentsView = observer(() => {

    const {agentStore} = useStore();
    const [selected, setSelected] = useState(null);
    const [createMode, setCreateMode] = useState(false);

    useEffect(() => {
        agentStore.loadAgents().then();
    }, [agentStore]);

    const builtinAgents = agentStore.agents.filter((a) => a.is_builtin);
    const customAgents = agentStore.agents.filter((a) => !a.is_builtin);

    if (selected) {
        return (
            <AgentDetail
                name={selected}
                onBack={() => {
                    setSelected(null);
                    agentStore.clearCurrent();
                    agentStore.loadAgents().then();
                }}
            />
        );
    }

    if (createMode) {
        return (
            <CreateAgent
                onBack={() => setCreateMode(false)}
                onCreated={(name) => {
                    setCreateMode(false);
                    setSelected(name);
                    agentStore.selectAgent(name).then();
                }}
            />
        );
    }

    if (agentStore.loading) return <Centered>Loading…</Centered>;

    return (
        <div className="h-full overflow-y-auto">
            {agentStore.toast && <Toast {...agentStore.toast} />}
            <div className="mx-auto max-w-5xl px-6 py-8">
                <div className="mb-6 flex items-center justify-between">
                    <Header/>
                    <FancyButton onClick={() => setCreateMode(true)}>
                        New Agent
                    </FancyButton>
                </div>

                {/* builtin agents */}
                {builtinAgents.length > 0 && (
                    <>
                        <SectionTitle>Built-in</SectionTitle>
                        <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {builtinAgents.map((a) => (
                                <AgentCard
                                    key={a.name}
                                    agent={a}
                                    onClick={() => {
                                        setSelected(a.name);
                                        agentStore.selectAgent(a.name).then();
                                    }}
                                />
                            ))}
                        </div>
                    </>
                )}

                {/* custom agents */}
                {customAgents.length > 0 && (
                    <>
                        <SectionTitle>Custom</SectionTitle>
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {customAgents.map((a) => (
                                <AgentCard
                                    key={a.name}
                                    agent={a}
                                    onClick={() => {
                                        setSelected(a.name);
                                        agentStore.selectAgent(a.name).then();
                                    }}
                                />
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
});

// ─── list-only components ───────────────────────────────────────────────────
const AgentCard = ({agent, onClick}) => {
    return (
        <button
            onClick={onClick}
            className="rounded-card group p-6 text-left"
        >
            <div className="mb-4 flex items-center gap-3">
                <Avatar seed={agent.name} size={44}/>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1">
                        <span className="truncate font-display text-base font-medium tracking-tight">
                            {agent.name}
                        </span>
                        {agent.is_builtin && (
                            <Lock className="size-3 shrink-0 text-muted-foreground/50"/>
                        )}
                    </div>
                </div>
            </div>
            {agent.description && (
                <p className="mb-3 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
                    {agent.description}
                </p>
            )}
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                {agent.tools.length > 0 ? (
                    <>
                        <Wrench className="size-3"/>
                        <span className="truncate">
                            {agent.tools.join(", ")}
                        </span>
                    </>
                ) : (
                    <span>no tools</span>
                )}
            </div>
        </button>
    );
}

const Header = () => {
    return (
        <div className="mb-6 flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-foreground/5 ring-1 ring-border/60">
                <Bot className="size-4 text-foreground/70"/>
            </span>
            <h1 className="h-display">Agents</h1>
        </div>
    );
}

const SectionTitle = ({children}) => {
    return (
        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.15em] text-foreground/45">
            {children}
        </div>
    );
}

export default AgentsView
