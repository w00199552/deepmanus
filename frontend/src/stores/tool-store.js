import {makeAutoObservable, runInAction} from "mobx";

import {getToolFile, getToolTree, listTools} from "@/services/tool-service";

/**
 * ToolStore — manages tool list + tool detail (file tree + content).
 * View → store → service. Mirrors SkillStore; adds `notFound` for built-in
 * tools (the tree endpoint 404s because they have no source files).
 */
export class ToolStore {
    tools = [];
    loading = false;
    error = null;

    // Tool detail state
    detailTree = null;
    detailFile = null;
    detailLoading = false;
    detailName = null;
    detailNotFound = false;

    constructor() {
        makeAutoObservable(this);
    }

    async loadTools() {
        this.loading = true;
        try {
            const data = await listTools();
            runInAction(() => {
                this.tools = data;
                this.loading = false;
            });
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
                this.loading = false;
            });
        }
    }

    async loadToolDetail(name) {
        runInAction(() => {
            this.detailName = name;
            this.detailLoading = true;
            this.detailTree = null;
            this.detailFile = null;
            this.detailNotFound = false;
        });
        try {
            const tree = await getToolTree(name);
            // Guard: if user switched to another tool while loading, discard.
            if (this.detailName !== name) return;
            runInAction(() => {
                this.detailTree = tree;
                this.detailLoading = false;
            });
            const toolYaml = this._findFile(tree, "tool.yaml");
            if (toolYaml) {
                await this.loadToolFile(name, toolYaml.path);
            }
        } catch {
            // Built-in tools have no files → 404. Anything else also lands here.
            if (this.detailName !== name) return;
            runInAction(() => {
                this.detailNotFound = true;
                this.detailLoading = false;
            });
        }
    }

    async loadToolFile(name, path) {
        try {
            const file = await getToolFile(name, path);
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
        this.detailNotFound = false;
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
