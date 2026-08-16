import axios from "@/services/axios.js";

class TopicService {
    service = import.meta.env.VITE_BACKEND_URL;

    async listTopics() {
        return await axios.get(`${this.service}/topics`);
    }

    async deleteTopic(topicId) {
        return await axios.delete(`${this.service}/topics/${encodeURIComponent(topicId)}`);
    }

    async resetTopic(topicId) {
        return await axios.post(`${this.service}/topics/${encodeURIComponent(topicId)}/reset`);
    }

    async cdTopic(topicId, path) {
        return await axios.post(`${this.service}/topics/${encodeURIComponent(topicId)}/cd`, {
            path
        });
    }

    async getTopicHistory(topicId) {
        return await axios.get(`${this.service}/topics/${encodeURIComponent(topicId)}/history`);
    }
}

export default new TopicService();
