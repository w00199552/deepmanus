import axios from "@/services/axios.js";

class ToolService {
    service = import.meta.env.VITE_BACKEND_URL;

    async listTools() {
        return await axios.get(`${this.service}/tools-api`);
    }

    async getToolTree(name) {
        return await axios.get(`${this.service}/tools-api/${encodeURIComponent(name)}/tree`);
    }

    async getToolFile(name, path) {
        return await axios.get(`${this.service}/tools-api/${encodeURIComponent(name)}/file`, {
            params: {path}
        });
    }
}

export default new ToolService();
