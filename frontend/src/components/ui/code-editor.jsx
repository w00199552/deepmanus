import Editor from "@monaco-editor/react";

/**
 * File extension → Monaco language mapping (shared across all CodeEditor users).
 */
export const LANG_MAP = {
    py: "python",
    js: "javascript",
    jsx: "javascript",
    ts: "typescript",
    tsx: "typescript",
    sh: "shell",
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    css: "css",
    html: "html",
    sql: "sql",
    md: "markdown",
    go: "go",
    rs: "rust",
    java: "java",
    c: "c",
    cpp: "cpp",
};

/**
 * Get Monaco language from a filename.
 */
export function langFromName(name) {
    const ext = name.split(".").pop()?.toLowerCase();
    return LANG_MAP[ext] || "plaintext";
}

/**
 * CodeEditor — Monaco editor wrapper, shadcn-style.
 *
 * @param {string}   value          code content
 * @param {string}   [language]     monaco language id (python/javascript/...)
 * @param {string}   [theme]        "dark" | "light" (from useTheme)
 * @param {boolean}  [readOnly]     read-only mode
 * @param {function} [onChange]     (value: string) => void
 * @param {string}   [path]         file path (monaco model uri for undo persistence)
 */
export function CodeEditor({
    value,
    language = "plaintext",
    theme = "dark",
    readOnly = false,
    onChange,
    path,
}) {
    return (
        <Editor
            value={value}
            language={language}
            theme={theme === "dark" ? "vs-dark" : "vs"}
            path={path ? `file:///${path}` : undefined}
            loading={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading editor…</div>}
            options={{
                readOnly,
                minimap: {enabled: false},
                fontSize: 13,
                lineHeight: 20,
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                wordWrap: "on",
                automaticLayout: true,
                tabSize: 4,
                padding: {top: 12, bottom: 12},
                smoothScrolling: true,
                cursorBlinking: "smooth",
                renderWhitespace: "selection",
                guides: {indentation: true},
            }}
            onChange={(val) => onChange?.(val ?? "")}
        />
    );
}
