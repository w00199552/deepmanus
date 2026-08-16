import {makeAutoObservable, runInAction} from "mobx";

import toolService from "@/services/tool-service.js";

export class ToolStore {
    tools = [];
    error = null;

    detailTree = null;
    detailFile = null;
    detailName = null;
    detailNotFound = false;

    constructor() {
        makeAutoObservable(this);
    }

    async loadTools() {
        try {
            const resp = await toolService.listTools();
            runInAction(() => {
                this.tools = resp.data || [];
            });
        } catch (e) {
            runInAction(() => {
                this.error = e.message;
            });
        }
    }

    async loadToolDetail(name) {
        runInAction(() => {
            this.detailName = name;
            this.detailTree = null;
            this.detailFile = null;
            this.detailNotFound = false;
        });
        try {
            const resp = await toolService.getToolTree(name);
            if (this.detailName !== name) return;
            const tree = resp.result;
            runInAction(() => {
                this.detailTree = tree;
            });
            const toolYaml = _findFile(tree, "tool.yaml");
            if (toolYaml) {
                await this.loadToolFile(name, toolYaml.path);
            }
        } catch {
            // 内置工具没有源文件（业务 fail）→ 显示"无文件"态。
            if (this.detailName !== name) return;
            runInAction(() => {
                this.detailNotFound = true;
            });
        }
    }

    async loadToolFile(name, path) {
        try {
            const resp = await toolService.getToolFile(name, path);
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
        this.detailNotFound = false;
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
