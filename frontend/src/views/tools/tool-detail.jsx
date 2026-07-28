import {useEffect} from "react";
import {observer} from "mobx-react-lite";
import {ChevronLeft, Lock, Wrench} from "lucide-react";
import MDEditor from "@uiw/react-md-editor";

import {useStore} from "@/hooks/use-store.jsx";
import {useTheme} from "@/hooks/use-theme.js";
import {LoadingState} from "@/components/ui/loading-state.jsx";
import {Tree} from "@/components/ui/tree.jsx";
import {CodeEditor, langFromName} from "@/components/ui/code-editor.jsx";

const ToolDetail = observer(({name, onBack}) => {
    const {toolStore: s} = useStore();
    const {isDark} = useTheme();

    useEffect(() => {
        s.loadToolDetail(name);
    }, [name, s]);

    if (s.detailLoading) return <LoadingState>Loading…</LoadingState>;

    // Built-in tools have no source files (tree endpoint 404s).
    if (s.detailNotFound) {
        return (
            <div className="flex h-full">
                <div className="flex w-56 shrink-0 flex-col border-r border-border/60 bg-sidebar/20">
                    <button
                        onClick={onBack}
                        className="flex items-center gap-1 px-4 py-3 text-sm text-muted-foreground transition hover:bg-foreground/5 hover:text-foreground"
                    >
                        <ChevronLeft className="size-4"/> Tools
                    </button>
                    <div className="px-4 py-2">
                        <div className="flex items-center gap-2">
                            <div className="flex size-8 items-center justify-center rounded-lg bg-foreground/5 ring-1 ring-border/60">
                                <Lock className="size-4 text-muted-foreground/50"/>
                            </div>
                            <span className="text-sm font-medium">{name}</span>
                        </div>
                    </div>
                </div>
                <div className="flex flex-1 items-center justify-center">
                    <div className="text-center">
                        <Lock className="mx-auto mb-3 size-8 text-muted-foreground/30"/>
                        <p className="text-sm text-muted-foreground">
                            Built-in tool — no source files to browse.
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full">
            {/* left: file tree */}
            <div className="flex w-56 shrink-0 flex-col border-r border-border/60 bg-sidebar/20">
                <button
                    onClick={onBack}
                    className="flex items-center gap-1 px-4 py-3 text-sm text-muted-foreground transition hover:bg-foreground/5 hover:text-foreground"
                >
                    <ChevronLeft className="size-4"/> Tools
                </button>
                <div className="px-4 py-2">
                    <div className="flex items-center gap-2">
                        <div className="flex size-8 items-center justify-center rounded-lg bg-foreground/5 ring-1 ring-border/60">
                            <Wrench className="size-4 text-foreground/70"/>
                        </div>
                        <span className="text-sm font-medium">{name}</span>
                    </div>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
                    <Tree
                        data={s.detailTree}
                        selectedPath={s.detailFile?.path}
                        onSelect={(node) => s.loadToolFile(name, node.path)}
                    />
                </div>
            </div>

            {/* right: file content */}
            <div className="min-h-0 flex-1 overflow-hidden">
                <div className="flex h-full flex-col">
                    {s.detailFile ? (
                        <>
                            <div
                                className="shrink-0 border-b border-border/60 px-4 py-2 text-[12px] text-muted-foreground">
                                {s.detailFile.name}
                            </div>
                            <div
                                className="min-h-0 flex-1 overflow-auto"
                                data-color-mode={isDark ? "dark" : "light"}
                            >
                                <FileContent file={s.detailFile} isDark={isDark}/>
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
});

export default ToolDetail;

// ─── File content renderer ──────────────────────────────────────────────────

function FileContent({file, isDark}) {
    if (file.file_type === "markdown") {
        return (
            <div className="h-full" data-color-mode={isDark ? "dark" : "light"}>
                <MDEditor
                    value={file.content}
                    height="100%"
                    preview="live"
                    data-color-mode={isDark ? "dark" : "light"}
                    style={{height: "100%"}}
                />
            </div>
        );
    }

    if (file.file_type === "code") {
        return (
            <CodeEditor
                value={file.content}
                language={langFromName(file.name)}
                theme={isDark ? "dark" : "light"}
                readOnly
                path={file.name}
            />
        );
    }

    return (
        <pre className="p-4 text-[13px] leading-relaxed text-muted-foreground/80">
            {file.content}
        </pre>
    );
}
