import axios from "@/services/axios.js";

class SkillService {
    service = import.meta.env.VITE_BACKEND_URL;

    async listSkills() {
        return await axios.get(`${this.service}/skills`);
    }

    async getSkillTree(name) {
        return await axios.get(`${this.service}/skills/${encodeURIComponent(name)}/tree`);
    }

    async getSkillFile(name, path) {
        return await axios.get(`${this.service}/skills/${encodeURIComponent(name)}/file`, {
            params: {path}
        });
    }
}

export default new SkillService();
