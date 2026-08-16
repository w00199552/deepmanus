import {makeAutoObservable, runInAction} from "mobx";

import topicService from "@/services/topic-service.js";

const LS_KEY = "openmanus.activeTopicId";

export const MAIN_TOPIC_ID = "main";

export class TopicStore {
    topics = [];
    activeTopicId = null;
    error = null;
    unread = {};

    constructor() {
        makeAutoObservable(this);
        this.activeTopicId = localStorage.getItem(LS_KEY) || MAIN_TOPIC_ID;
    }

    get active() {
        return this.topics.find((t) => t.id === this.activeTopicId) || null;
    }

    get sortedTopics() {
        return [...this.topics].sort((a, b) => {
            const am = a.id === MAIN_TOPIC_ID ? 1 : 0;
            const bm = b.id === MAIN_TOPIC_ID ? 1 : 0;
            if (am !== bm) return bm - am;
            const ta = _ts(a.updated_at) || _ts(a.created_at) || 0;
            const tb = _ts(b.updated_at) || _ts(b.created_at) || 0;
            return tb - ta;
        });
    }

    get mainTopic() {
        return this.sortedTopics.filter((t) => t.id === MAIN_TOPIC_ID);
    }

    get taskTopics() {
        return this.sortedTopics.filter((t) => t.id !== MAIN_TOPIC_ID);
    }

    async load() {
        this.error = null;
        try {
            const resp = await topicService.listTopics();
            runInAction(() => {
                this.topics = resp.data || [];
                if (
                    this.activeTopicId &&
                    this.activeTopicId !== MAIN_TOPIC_ID &&
                    !this.topics.some((t) => t.id === this.activeTopicId)
                ) {
                    this._setActive(MAIN_TOPIC_ID);
                }
            });
            return this.topics;
        } catch (e) {
            runInAction(() => {
                this.error = e.message || String(e);
            });
            return [];
        }
    }

    select(topicId) {
        this._setActive(topicId);
    }

    async remove(topicId) {
        await topicService.deleteTopic(topicId);
        runInAction(() => {
            this.topics = this.topics.filter((t) => t.id !== topicId);
            if (this.activeTopicId === topicId) {
                this._setActive(MAIN_TOPIC_ID);
            }
        });
    }

    async reset(topicId) {
        await topicService.resetTopic(topicId);
    }

    _setActive(topicId) {
        this.activeTopicId = topicId;
        localStorage.setItem(LS_KEY, topicId);
    }

    bumpActivity(topicId, { preview, speaker, unread } = {}) {
        const t = this.topics.find((x) => x.id === topicId);
        if (!t) return;
        if (preview !== undefined) t.preview = preview;
        if (unread !== undefined) this.unread[topicId] = unread;
    }

    markStatus(topicId, status) {
        const t = this.topics.find((x) => x.id === topicId);
        if (t) t.status = status;
    }

    markRunning(topicId) {
        this.markStatus(topicId, "running");
    }

    unreadCount(topicId) {
        return this.unread[topicId] || 0;
    }
}

function _ts(s) {
    if (!s) return 0;
    return Date.parse(String(s).replace(" ", "T")) || 0;
}
