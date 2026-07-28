/**
 * Tool service — list tools + browse tool files (tree + content).
 * Backed by backend `/tools-api` (see api/tools.py).
 */

const BACKEND = (import.meta.env && import.meta.env.VITE_BACKEND_URL) || "";

/** List all tools (built-in + user-defined). */
export async function listTools() {
    const res = await fetch(`${BACKEND}/tools-api`);
    if (!res.ok) throw new Error(`listTools: ${res.status}`);
    return res.json();
}

/** Get the file tree of a user tool. 404 for built-in tools (no files). */
export async function getToolTree(name) {
    const res = await fetch(
        `${BACKEND}/tools-api/${encodeURIComponent(name)}/tree`
    );
    if (!res.ok) throw new Error(`getToolTree: ${res.status}`);
    return res.json();
}

/** Read a single file from a tool directory. */
export async function getToolFile(name, path) {
    const res = await fetch(
        `${BACKEND}/tools-api/${encodeURIComponent(name)}/file?path=${encodeURIComponent(path)}`
    );
    if (!res.ok) throw new Error(`getToolFile: ${res.status}`);
    return res.json();
}
