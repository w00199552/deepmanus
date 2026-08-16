import axios from "@/services/axios.js";

class SandboxService {
    service = import.meta.env.VITE_BACKEND_URL;

    async getTree(workdir = null) {
        return await axios.get(`${this.service}/sandbox/tree`, {
            params: {workdir}
        });
    }

    async getChildren(path, workdir = null) {
        return await axios.get(`${this.service}/sandbox/children`, {
            params: {path, workdir}
        });
    }

    async readFile(path, workdir = null) {
        return await axios.get(`${this.service}/sandbox/read`, {
            params: {path, workdir}
        });
    }

    async writeFile(path, content, workdir = null) {
        return await axios.put(`${this.service}/sandbox/write`, {
            path,
            content,
            workdir,
        });
    }

    async deletePath(path, workdir = null) {
        return await axios.delete(`${this.service}/sandbox/delete`, {
            data: {path, workdir}
        });
    }

    async createDir(path, workdir = null) {
        return await axios.post(`${this.service}/sandbox/mkdir`, {
            path,
            workdir,
        });
    }

    async createFile(path, workdir = null) {
        return await axios.post(`${this.service}/sandbox/create`, {
            path,
            workdir,
        });
    }

    getWatchUrl(workdir = null) {
        const base = this.service || "";
        return workdir
            ? `${base}/sandbox/watch?workdir=${encodeURIComponent(workdir)}`
            : `${base}/sandbox/watch`;
    }
}

export default new SandboxService();
