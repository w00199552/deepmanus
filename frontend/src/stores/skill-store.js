import {makeAutoObservable, runInAction} from "mobx";

import {getSkillFile, getSkillTree, listSkills} from "@/services/agent-service";

/**
 * SkillStore — manages skill list + skill detail (file tree + content).
 * View → store → service.
 */
export class SkillStore {
    skills = [];
    loading = false;
    error = null;

    // Skill detail state
    detailTree = null;
    detailFile = null;
    detailLoading = false;
    detailName = null;

    constructor() {
        makeAutoObservable(this);
    }

    async loadSkills() {
        this.loading = true;
        try {
            const data = await listSkills();
            runInAction(() => {
                this.skills = data;
                this.loading = false;
            });
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
                this.loading = false;
            });
        }
    }

    async loadSkillDetail(name) {
        this.detailName = name;
        this.detailLoading = true;
        this.detailTree = null;
        this.detailFile = null;
        try {
            const tree = await getSkillTree(name);
            runInAction(() => {
                this.detailTree = tree;
                this.detailLoading = false;
            });
            // Auto-select SKILL.md
            const skillMd = this._findFile(tree, "SKILL.md");
            if (skillMd) {
                await this.loadSkillFile(name, skillMd.path);
            }
        } catch {
            runInAction(() => {
                this.detailLoading = false;
            });
        }
    }

    async loadSkillFile(name, path) {
        try {
            const file = await getSkillFile(name, path);
            runInAction(() => {
                this.detailFile = file;
            });
        } catch {
            /* ignore */
        }
    }

    clearDetail() {
        this.detailTree = null;
        this.detailFile = null;
        this.detailName = null;
        this.detailLoading = false;
    }

    _findFile(node, name) {
        if (node.type === "file" && node.name === name) return node;
        for (const child of node.children || []) {
            const found = this._findFile(child, name);
            if (found) return found;
        }
        return null;
    }
}
