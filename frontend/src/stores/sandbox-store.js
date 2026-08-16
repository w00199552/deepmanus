import {makeAutoObservable, runInAction} from "mobx";

import sandboxService from "@/services/sandbox-service.js";
import topicService from "@/services/topic-service.js";

export class SandboxStore {
    _topicStore = null;

    workdir = "";

    constructor() {
        makeAutoObservable(this);
    }

    setTopicStore(s) {
        this._topicStore = s;
    }

    syncFromTopic() {
        if (!this._topicStore) return;
        const topic = this._topicStore.active;
        if (topic && topic.workdir) {
            this.workdir = topic.workdir;
        }
    }

    async cd(topicId, path) {
        const resp = await topicService.cdTopic(topicId, path);
        const body = resp.result;
        if (body && body.workdir && body.action === "cd") {
            runInAction(() => {
                this.workdir = body.workdir;
                if (this._topicStore) {
                    const topic = this._topicStore.active;
                    if (topic) topic.workdir = body.workdir;
                }
            });
        }
        return body;
    }

    async loadTree() {
        const resp = await sandboxService.getTree(this.workdir || null);
        return resp.result;
    }

    async loadChildren(dirPath) {
        const resp = await sandboxService.getChildren(dirPath, this.workdir || null);
        return resp.result?.children || [];
    }

    async loadFile(path) {
        const resp = await sandboxService.readFile(path, this.workdir || null);
        return resp.result;
    }

    async saveFile(path, content) {
        const resp = await sandboxService.writeFile(path, content, this.workdir || null);
        return resp.result;
    }

    async deletePath(path) {
        const resp = await sandboxService.deletePath(path, this.workdir || null);
        return resp.result;
    }

    async createDir(path) {
        const resp = await sandboxService.createDir(path, this.workdir || null);
        return resp.result;
    }

    async createFile(path) {
        const resp = await sandboxService.createFile(path, this.workdir || null);
        return resp.result;
    }

    get watchUrl() {
        return sandboxService.getWatchUrl(this.workdir || null);
    }
}
