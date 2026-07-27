import {useCallback, useEffect, useState} from "react";
import {
    ChevronLeft,
    Loader2,
    Sparkles,
} from "lucide-react";
import MDEditor from "@uiw/react-md-editor";
import {Highlight, themes} from "prism-react-renderer";

import {useTheme} from "@/hooks/use-theme.js";
import {getSkillFile, getSkillTree} from "@/services/agent-service.js";
import {Tree} from "@/components/ui/tree.jsx";
import {cn} from "@/lib/utils.js";

const SkillDetail = ({name, onBack}) => {
    const {isDark} = useTheme();
    const colorMode = isDark ? "dark" : "light";
    const [tree, setTree] = useState(null);
    const [file, setFile] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        getSkillTree(name)
            .then((data) => {
                setTree(data);
                setLoading(false);
                const skillMd = findFile(data, "SKILL.md");
                if (skillMd) loadFile(skillMd.path);
            })
            .catch(() => setLoading(false));
    }, [name]);

    const loadFile = useCallback(
        async (path) => {
            try {
                const f = await getSkillFile(name, path);
                setFile(f);
            } catch {
                /* ignore */
            }
        },
        [name]
    );

    if (loading)
        return (
            <Centered>
                <Loader2 className="size-4 animate-spin"/> Loading…
            </Centered>
        );

    return (
        <div className="flex h-full">
            {/* left: file tree */}
            <div className="flex w-56 shrink-0 flex-col border-r border-border/60 bg-sidebar/20">
                <button
                    onClick={onBack}
                    className="flex items-center gap-1 px-4 py-3 text-sm text-muted-foreground transition hover:bg-foreground/5 hover:text-foreground"
                >
                    <ChevronLeft className="size-4"/> Skills
                </button>
                <div className="px-4 py-2">
                    <div className="flex items-center gap-2">
                        <div
                            className="flex size-8 items-center justify-center rounded-lg bg-foreground/5 ring-1 ring-border/60">
                            <Sparkles className="size-4 text-foreground/70"/>
                        </div>
                        <span className="text-sm font-medium">{name}</span>
                    </div>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
                    {tree && (
                        <Tree
                            data={tree}
                            selectedPath={file?.path}
                            onSelect={(node) => loadFile(node.path)}
                        />
                    )}
                </div>
            </div>

            {/* right: file content */}
            <div className="min-h-0 flex-1 overflow-hidden">
                <div className="flex h-full flex-col">
                    {file ? (
                        <>
                            <div
                                className="shrink-0 border-b border-border/60 px-4 py-2 text-[12px] text-muted-foreground">
                                {file.name}
                            </div>
                            <div
                                className="min-h-0 flex-1 overflow-auto"
                                data-color-mode={colorMode}
                            >
                                <FileContent file={file}/>
                            </div>
                        </>
                    ) : (
                        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                            Select a file to view
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default SkillDetail;

// ─── File content renderer ──────────────────────────────────────────────────

function FileContent({file}) {
    const {isDark} = useTheme();
    const colorMode = isDark ? "dark" : "light";
    if (file.file_type === "markdown") {
        return (
            <div className="h-full" data-color-mode={colorMode}>
                <MDEditor
                    value={file.content}
                    height="100%"
                    preview="live"
                    data-color-mode={colorMode}
                    style={{height: "100%"}}
                />
            </div>
        );
    }

    if (file.file_type === "code") {
        const ext = file.name.split(".").pop()?.toLowerCase() || "text";
        const langMap = {
            py: "python", js: "javascript", jsx: "jsx", ts: "typescript",
            tsx: "tsx", sh: "bash", json: "json", yaml: "yaml", yml: "yaml",
            css: "css", html: "markup", sql: "sql",
        };
        const lang = langMap[ext] || "text";

        return (
            <Highlight
                theme={isDark ? themes.vsDark : themes.vsLight}
                code={file.content}
                language={lang}
            >
                {({className, style, tokens, getLineProps, getTokenProps}) => (
                    <pre
                        className={cn(className, "m-0 p-4 text-[13px] leading-relaxed")}
                        style={{...style, background: "transparent"}}
                    >
                        {tokens.map((line, i) => {
                            const lineProps = getLineProps({line});
                            return (
                                <div key={i} {...lineProps}>
                                    <span
                                        className="mr-3 inline-block w-8 select-none text-right text-muted-foreground/30">
                                        {i + 1}
                                    </span>
                                    {line.map((token, key) => (
                                        <span key={key} {...getTokenProps({token})} />
                                    ))}
                                </div>
                            );
                        })}
                    </pre>
                )}
            </Highlight>
        );
    }

    return (
        <pre className="p-4 text-[13px] leading-relaxed text-muted-foreground/80">
            {file.content}
        </pre>
    );
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function findFile(node, name) {
    if (node.type === "file" && node.name === name) return node;
    for (const child of node.children || []) {
        const found = findFile(child, name);
        if (found) return found;
    }
    return null;
}

function Centered({children}) {
    return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {children}
        </div>
    );
}
