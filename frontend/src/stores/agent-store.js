import {makeAutoObservable, runInAction} from "mobx";

import agentService from "@/services/agent-service.js";
import skillService from "@/services/skill-service.js";

export class AgentStore {
    agents = [];
    tools = [];
    skills = [];
    current = null;
    error = null;

    promptDraft = "";
    descriptionDraft = "";
    toolDraft = new Set();
    skillDraft = new Set();
    avatarReloadSignal = 0;
    presetList = [];
    presetListLoaded = false;

    constructor() {
        makeAutoObservable(this);
    }

    async loadAgents() {
        try {
            const resp = await agentService.listAgents();
            runInAction(() => {
                this.agents = resp.data || [];
            });
            return this.agents;
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
            return [];
        }
    }

    async loadTools() {
        try {
            const resp = await agentService.listMetaTools();
            runInAction(() => {
                this.tools = resp.data || [];
            });
        } catch {
            /* toast 已由 axios 拦截器处理 */
        }
    }

    async loadSkills() {
        try {
            const resp = await skillService.listSkills();
            runInAction(() => {
                this.skills = resp.data || [];
            });
        } catch {
            /* toast 已由 axios 拦截器处理 */
        }
    }

    async selectAgent(name) {
        try {
            const [agentResp, toolsResp, skillsResp] = await Promise.all([
                agentService.getAgent(name),
                agentService.listMetaTools(),
                skillService.listSkills(),
            ]);
            runInAction(() => {
                this.current = agentResp.result;
                this.tools = toolsResp.data || [];
                this.skills = skillsResp.data || [];
                this.promptDraft = this.current?.prompt || "";
                this.descriptionDraft = this.current?.description || "";
                this.toolDraft = new Set(this.current?.tools || []);
                this.skillDraft = new Set(this.current?.skills || []);
            });
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
        }
    }

    clearCurrent() {
        this.current = null;
    }

    setPromptDraft(text) {
        this.promptDraft = text;
    }

    setDescriptionDraft(text) {
        this.descriptionDraft = text;
    }

    toggleTool(name) {
        if (this.toolDraft.has(name)) this.toolDraft.delete(name);
        else this.toolDraft.add(name);
    }

    toggleSkill(name) {
        if (this.skillDraft.has(name)) this.skillDraft.delete(name);
        else this.skillDraft.add(name);
    }

    async save() {
        if (!this.current) return false;
        try {
            await agentService.updateAgent(this.current.name, {
                prompt: this.promptDraft,
                description: this.descriptionDraft,
                tools: [...this.toolDraft],
                skills: [...this.skillDraft],
            });
            await this.selectAgent(this.current.name);
            return true;
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
            return false;
        }
    }

    async loadAvatarPresets() {
        if (this.presetListLoaded) return this.presetList;
        try {
            const resp = await agentService.listAvatarPresets();
            runInAction(() => {
                this.presetList = resp.result?.presets || [];
                this.presetListLoaded = true;
            });
            return this.presetList;
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
            return [];
        }
    }

    async setAvatar(presetId) {
        if (!this.current) return false;
        try {
            const resp = await agentService.regenerateAvatar(this.current.name, presetId);
            const applied = resp.result?.avatar;
            runInAction(() => {
                if (this.current && applied) this.current.avatar = applied;
                const inList = this.agents.find((a) => a.name === this.current?.name);
                if (inList && applied) inList.avatar = applied;
                this.avatarReloadSignal++;
            });
            return true;
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
            return false;
        }
    }

    async create(name, prompt, tools, skills = [], description = "") {
        try {
            await agentService.createAgent({name, prompt, tools, skills, description});
            await this.loadAgents();
            return true;
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
            return false;
        }
    }

    async remove(name) {
        try {
            await agentService.deleteAgent(name);
            await this.loadAgents();
            return true;
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
            return false;
        }
    }
}
