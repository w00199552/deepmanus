import axios from "@/services/axios.js";

class SessionService {
    service = import.meta.env.VITE_BACKEND_URL;

    async createSession({title, kind = "root", name = null, workdir = null, topic_id = "main", metadata = {}}) {
        return await axios.post(`${this.service}/sessions`, {
            title,
            kind,
            name,
            workdir,
            topic_id,
            metadata,
        });
    }

    async listSessions({kind = null, topic_id = null} = {}) {
        return await axios.get(`${this.service}/sessions`, {
            params: {kind, topic_id}
        });
    }

    async getSession(sessionId) {
        return await axios.get(`${this.service}/sessions/${encodeURIComponent(sessionId)}`);
    }

    async updateSession(sessionId, {title, status, workdir, metadata}) {
        return await axios.patch(`${this.service}/sessions/${encodeURIComponent(sessionId)}`, {
            title,
            status,
            workdir,
            metadata,
        });
    }

    async setPreview(sessionId, preview, speaker = null) {
        return await axios.post(`${this.service}/sessions/${encodeURIComponent(sessionId)}/preview`, {
            preview,
            speaker,
        });
    }

    async resetSession(sessionId) {
        return await axios.post(`${this.service}/sessions/${encodeURIComponent(sessionId)}/reset`);
    }

    async deleteSession(sessionId) {
        return await axios.delete(`${this.service}/sessions/${encodeURIComponent(sessionId)}`);
    }

    async getWhiteboard(sessionId) {
        return await axios.get(`${this.service}/sessions/${encodeURIComponent(sessionId)}/whiteboard`);
    }
}

export default new SessionService();
