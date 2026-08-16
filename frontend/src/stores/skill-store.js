import {makeAutoObservable, runInAction} from "mobx";

import skillService from "@/services/skill-service.js";

export class SkillStore {
    skills = [];
    error = null;

    detailTree = null;
    detailFile = null;
    detailName = null;

    constructor() {
        makeAutoObservable(this);
    }

    async loadSkills() {
        try {
            const resp = await skillService.listSkills();
            runInAction(() => {
                this.skills = resp.data || [];
            });
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
        }
    }

    async loadSkillDetail(name) {
        runInAction(() => {
            this.detailName = name;
            this.detailTree = null;
            this.detailFile = null;
        });
        try {
            const resp = await skillService.getSkillTree(name);
            if (this.detailName !== name) return;
            const tree = resp.result;
            runInAction(() => {
                this.detailTree = tree;
            });
            const skillMd = _findFile(tree, "SKILL.md");
            if (skillMd) {
                await this.loadSkillFile(name, skillMd.path);
            }
        } catch {
            /* toast 已由 axios 拦截器处理 */
        }
    }

    async loadSkillFile(name, path) {
        try {
            const resp = await skillService.getSkillFile(name, path);
            runInAction(() => {
                this.detailFile = resp.result;
            });
        } catch {
            /* toast 已由 axios 拦截器处理 */
        }
    }

    clearDetail() {
        this.detailTree = null;
        this.detailFile = null;
        this.detailName = null;
    }
}

function _findFile(node, name) {
    if (node.type === "file" && node.name === name) return node;
    for (const child of node.children || []) {
        const found = _findFile(child, name);
        if (found) return found;
    }
    return null;
}
