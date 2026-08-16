import {createContext, createElement} from "react";

import {TopicStore} from "@/stores/topic-store.js";
import {AgentStore} from "@/stores/agent-store.js";
import {SkillStore} from "@/stores/skill-store.js";
import {ToolStore} from "@/stores/tool-store.js";
import {SandboxStore} from "@/stores/sandbox-store.js";
import {AgentRuntime} from "@/runtime/agent-runtime.js";

export class RootStore {
    topics;
    runtime;
    sandbox;
    agentStore;
    skillStore;
    toolStore;

    constructor() {
        this.topics = new TopicStore();
        this.runtime = new AgentRuntime();
        this.sandbox = new SandboxStore();
        this.agentStore = new AgentStore();
        this.skillStore = new SkillStore();
        this.toolStore = new ToolStore();
        this.runtime.setTopicStore(this.topics);
        this.sandbox.setTopicStore(this.topics);
        this.runtime.setSandboxStore(this.sandbox);
    }
}

export const rootStore = new RootStore();

export const MobxContext = createContext(rootStore);

export function StoreProvider({children}) {
    return createElement(MobxContext.Provider, {value: rootStore}, children);
}
