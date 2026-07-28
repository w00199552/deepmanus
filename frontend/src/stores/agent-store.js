import {makeAutoObservable, runInAction} from "mobx";
import {toast as sonnerToast} from "sonner";

import {getAgent, listAgents, listSkills, listTools,} from "@/services/agent-service";

const BACKEND = (import.meta.env && import.meta.env.VITE_BACKEND_URL) || "";

/**
 * AgentStore — manages agent configurations (list / detail / tools / save).
 * Views call actions here, never services directly.
 */
export class AgentStore {

    agents = [];
    tools = [];
    skills = [];
    current = null;
    loading = false;
    saving = false;
    error = null;

    // edit drafts
    promptDraft = "";
    descriptionDraft = "";
    toolDraft = new Set();
    skillDraft = new Set();
    avatarLoading = false;
    // bumped after any avatar changes; <Avatar> subscribes and uses it to
    // cache-bust its <img> URL. Centralized here so callers never pass a
    // version prop — every avatar on screen refreshes automatically.
    avatarReloadSignal = 0;
    // bundled avatar presets (offline): [{id, file, seed, url}]
    presetList = [];
    presetListLoaded = false;

    _showToast(type, message) {
        // sonner manages its own auto-dismiss; no store state needed.
        if (type === "error") sonnerToast.error(message);
        else sonnerToast.success(message);
    }

    constructor() {
        makeAutoObservable(this);
    }

    /** Load agent list (metadata only). */
    async loadAgents() {
        this.loading = true;
        try {
            const data = await listAgents();
            console.log(data);
            runInAction(() => {
                this.agents = data;
                this.loading = false;
            });
            return data;
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
                this.loading = false;
            });
        }
    }

    /** Load all available tools (built-in + user). */
    async loadTools() {
        try {
            const data = await listTools();
            runInAction(() => {
                this.tools = data;
            });
        } catch {
            /* ignore */
        }
    }

    /** Load all available skills. */
    async loadSkills() {
        try {
            const data = await listSkills();
            runInAction(() => {
                this.skills = data;
            });
        } catch {
            /* ignore */
        }
    }

    /** Open an agent's detail (loads full config + tools + skills). */
    async selectAgent(name) {
        this.loading = true;
        try {
            const [agent, tools, skills] = await Promise.all([
                getAgent(name),
                listTools(),
                listSkills(),
            ]);
            runInAction(() => {
                this.current = agent;
                this.tools = tools;
                this.skills = skills;
                this.promptDraft = agent.prompt || "";
                this.descriptionDraft = agent.description || "";
                this.toolDraft = new Set(agent.tools || []);
                this.skillDraft = new Set(agent.skills || []);
                this.loading = false;
            });
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
                this.loading = false;
            });
        }
    }

    /** Clear the current detail. */
    clearCurrent() {
        this.current = null;
    }

    // ─── draft mutators (called by view) ────────────────────────────────────

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

    // ─── save ────────────────────────────────────────────────────────────────

    /** Save prompt + tools to backend (writes agent.yaml + prompt.md on disk). */
    async save() {
        if (!this.current) return;
        this.saving = true;
        try {
            const res = await fetch(
                `${BACKEND}/agents/${encodeURIComponent(this.current.name)}`,
                {
                    method: "PUT",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        prompt: this.promptDraft,
                        description: this.descriptionDraft,
                        tools: [...this.toolDraft],
                        skills: [...this.skillDraft],
                    }),
                }
            );
            if (!res.ok) throw new Error(`save failed: ${res.status}`);
            await this.selectAgent(this.current.name);
            this._showToast("success", "Agent saved successfully");
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
            this._showToast("error", e.message || "Save failed");
        }
        runInAction(() => {
            this.saving = false;
        });
    }

    /** Load bundled avatar presets (offline). Lazy, cached. */
    async loadAvatarPresets() {
        if (this.presetListLoaded) return this.presetList;
        try {
            const res = await fetch(`${BACKEND}/agents/avatar-presets`);
            if (!res.ok) throw new Error(`load presets failed: ${res.status}`);
            const j = await res.json();
            runInAction(() => {
                this.presetList = j.presets || [];
                this.presetListLoaded = true;
            });
            return this.presetList;
        } catch (e) {
            this._showToast("error", e.message || "头像预设加载失败");
            return [];
        }
    }

    /**
     * Apply an avatar preset to the current agent.
     * @param {string} presetId  e.g. "07"; if omitted, backend picks a random preset
     */
    async setAvatar(presetId) {
        if (!this.current || this.avatarLoading) return;
        runInAction(() => {
            this.avatarLoading = true;
        });
        try {
            const res = await fetch(
                `${BACKEND}/agents/${encodeURIComponent(this.current.name)}/avatar/regenerate`,
                {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({preset_id: presetId || null}),
                }
            );
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `set avatar failed: ${res.status}`);
            }
            const j = await res.json();
            runInAction(() => {
                // Update local data so cards/lists reflect the new avatar.
                if (this.current) this.current.avatar = j.avatar;
                const inList = this.agents.find((a) => a.name === this.current?.name);
                if (inList) inList.avatar = j.avatar;
                // Bump the signal so every <Avatar> on screen cache-busts.
                this.avatarReloadSignal++;
            });
            this._showToast("success", "头像已更新");
        } catch (e) {
            this._showToast("error", e.message || "头像更新失败");
        } finally {
            runInAction(() => {
                this.avatarLoading = false;
            });
        }
    }

    /** Create a new agent on disk. Returns true on success. */
    async create(name, prompt, tools, skills = [], description = "") {
        this.saving = true;
        try {
            const res = await fetch(`${BACKEND}/agents`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    name,
                    prompt,
                    tools,
                    skills,
                    description,
                }),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `create failed: ${res.status}`);
            }
            await this.loadAgents();
            this._showToast("success", `Agent "${name}" created`);
            return true;
        } catch (e) {
            this._showToast("error", e.message || "Create failed");
            return false;
        }
        runInAction(() => {
            this.saving = false;
        });
    }

    /** Delete a custom agent. Returns true on success. */
    async remove(name) {
        try {
            const res = await fetch(
                `${BACKEND}/agents/${encodeURIComponent(name)}`,
                {method: "DELETE"}
            );
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `delete failed: ${res.status}`);
            }
            await this.loadAgents();
            this._showToast("success", `Agent "${name}" deleted`);
            return true;
        } catch (e) {
            this._showToast("error", e.message || "Delete failed");
            return false;
        }
    }
}
