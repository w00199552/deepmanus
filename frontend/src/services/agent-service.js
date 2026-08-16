import axios from "@/services/axios.js";

class AgentService {
    service = import.meta.env.VITE_BACKEND_URL;

    async listAgents() {
        return await axios.get(`${this.service}/agents`);
    }

    async getAgent(name) {
        return await axios.get(`${this.service}/agents/${encodeURIComponent(name)}`);
    }

    async createAgent({name, prompt, tools, skills, description}) {
        return await axios.post(`${this.service}/agents`, {
            name,
            prompt,
            tools,
            skills,
            description,
        });
    }

    async updateAgent(name, {prompt, description, tools, skills}) {
        return await axios.put(`${this.service}/agents/${encodeURIComponent(name)}`, {
            prompt,
            description,
            tools,
            skills,
        });
    }

    async deleteAgent(name) {
        return await axios.delete(`${this.service}/agents/${encodeURIComponent(name)}`);
    }

    async regenerateAvatar(name, presetId = null) {
        return await axios.post(
            `${this.service}/agents/${encodeURIComponent(name)}/avatar/regenerate`,
            {preset_id: presetId}
        );
    }

    async listAvatarPresets() {
        return await axios.get(`${this.service}/agents/avatar-presets`);
    }

    async listMetaTools() {
        return await axios.get(`${this.service}/agents/meta/tools`);
    }

    async listMetaSkills() {
        return await axios.get(`${this.service}/agents/meta/skills`);
    }
}

export default new AgentService();
