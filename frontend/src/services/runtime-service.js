import axios from "@/services/axios.js";

class RuntimeService {
    service = import.meta.env.VITE_BACKEND_URL;

    async postTopicMessage(topicId, content, targetAgent = null, signal = null) {
        return await axios.post(
            `${this.service}/topics/${encodeURIComponent(topicId)}/messages`,
            {content, target_agent: targetAgent},
            {signal}
        );
    }

    async postSessionMessage(sessionId, content, targetAgent = null) {
        return await axios.post(
            `${this.service}/sessions/${encodeURIComponent(sessionId)}/messages`,
            {content, target_agent: targetAgent}
        );
    }

    async getHealth() {
        return await axios.get(`${this.service}/health`);
    }

    getStreamUrl({topic = null, sessions = null} = {}) {
        const base = this.service || "";
        if (topic) {
            return `${base}/stream?topic=${encodeURIComponent(topic)}`;
        }
        if (sessions && sessions.length) {
            const ids = sessions.map(encodeURIComponent).join(",");
            return `${base}/stream?sessions=${ids}`;
        }
        return `${base}/stream`;
    }
}

export default new RuntimeService();
