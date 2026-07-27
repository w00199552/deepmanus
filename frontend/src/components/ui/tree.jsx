import {useState, useCallback} from "react";
import {
    ChevronRight,
    File,
    FileCode,
    FileText,
    Folder,
    FolderOpen,
    Loader2,
} from "lucide-react";
import {Collapsible, CollapsibleContent, CollapsibleTrigger} from "@/components/ui/collapsible";
import {cn} from "@/lib/utils";

/**
 * Tree — recursive file/folder tree, shadcn-style.
 *
 * Built on Radix Collapsible for expand/collapse (animation + a11y),
 * lucide icons for file/folder visuals, and tailwind for styling.
 * Zero extra dependencies beyond what's already installed.
 *
 * Inspired by ant.design Tree's API, adapted to the shadcn ecosystem.
 *
 * @param {object}    data                root tree node
 * @param {string}    [selectedPath]      currently selected file path
 * @param {function}  [onSelect]          (node) => void — file node clicked
 * @param {function}  [onExpand]          (node, isExpanded) => void
 * @param {function}  [loadData]          async (node) => children[] — lazy load
 * @param {boolean}   [checkable=false]   show checkboxes
 * @param {function}  [onCheck]           (checkedPaths: Set) => void
 * @param {boolean}   [defaultExpandAll=true] expand all dirs on mount
 */

// ─── Tree (top-level) ───────────────────────────────────────────────────────

export function Tree({
    data,
    selectedPath,
    onSelect,
    onExpand,
    loadData,
    checkable = false,
    onCheck,
    defaultExpandAll = true,
}) {
    const [expandedPaths, setExpandedPaths] = useState(() => {
        const dirs = new Set();
        if (defaultExpandAll) collectDirs(data, dirs);
        return dirs;
    });
    const [checkedPaths, setCheckedPaths] = useState(new Set());

    const handleToggle = useCallback(
        (node, willOpen) => {
            setExpandedPaths((prev) => {
                const next = new Set(prev);
                if (willOpen) next.add(node.path);
                else next.delete(node.path);
                return next;
            });
            onExpand?.(node, willOpen);
        },
        [onExpand]
    );

    const handleCheck = useCallback(
        (node, checked) => {
            setCheckedPaths((prev) => {
                const next = new Set(prev);
                if (checked) {
                    next.add(node.path);
                    // check all descendants
                    walkDescendants(node, (child) => next.add(child.path));
                } else {
                    next.delete(node.path);
                    walkDescendants(node, (child) => next.delete(child.path));
                }
                onCheck?.(next);
                return next;
            });
        },
        [onCheck]
    );

    if (!data) return null;

    // Root renders its children directly (no indent for the root container).
    if (data.type === "dir" && data.children) {
        return (
            <div>
                {data.children.map((child) => (
                    <TreeNode
                        key={child.path || child.name}
                        node={child}
                        depth={0}
                        expandedPaths={expandedPaths}
                        selectedPath={selectedPath}
                        onSelect={onSelect}
                        onToggle={handleToggle}
                        loadData={loadData}
                        checkable={checkable}
                        checkedPaths={checkedPaths}
                        onCheck={handleCheck}
                    />
                ))}
            </div>
        );
    }

    // Single-node root
    return (
        <TreeNode
            node={data}
            depth={0}
            expandedPaths={expandedPaths}
            selectedPath={selectedPath}
            onSelect={onSelect}
            onToggle={handleToggle}
            loadData={loadData}
            checkable={checkable}
            checkedPaths={checkedPaths}
            onCheck={handleCheck}
        />
    );
}

// ─── TreeNode (recursive branch) ────────────────────────────────────────────

function TreeNode({
    node,
    depth,
    expandedPaths,
    selectedPath,
    onSelect,
    onToggle,
    loadData,
    checkable,
    checkedPaths,
    onCheck,
}) {
    const isDir = node.type === "dir" || (!node.isLeaf && (node.children?.length > 0 || !!loadData));
    const isOpen = expandedPaths.has(node.path);
    const isSelected = selectedPath === node.path;
    const isChecked = checkedPaths.has(node.path);
    const isDisabled = node.disabled;

    // Async loading state
    const [loading, setLoading] = useState(false);
    const [loadedChildren, setLoadedChildren] = useState(null);

    const children = loadedChildren || node.children;

    const handleTriggerClick = async () => {
        if (isDisabled) return;
        if (!isDir) {
            onSelect?.(node);
            return;
        }
        // Directory: toggle expand
        const willOpen = !isOpen;
        if (willOpen && !children && loadData) {
            setLoading(true);
            try {
                const kids = await loadData(node);
                setLoadedChildren(kids);
            } catch {
                /* ignore */
            } finally {
                setLoading(false);
            }
        }
        onToggle(node, willOpen);
    };

    return (
        <Collapsible open={isOpen} onOpenChange={(open) => onToggle(node, open)}>
            {/* Node row */}
            <div
                className="flex items-center"
                style={{paddingLeft: `${depth * 16}px`}}
            >
                {/* Checkbox (optional) */}
                {checkable && (
                    <input
                        type="checkbox"
                        checked={isChecked}
                        disabled={isDisabled}
                        onChange={(e) => onCheck(node, e.target.checked)}
                        className="mr-1.5 size-3.5 shrink-0 rounded border-border accent-accent"
                    />
                )}

                <CollapsibleTrigger asChild>
                    <button
                        onClick={handleTriggerClick}
                        disabled={isDisabled}
                        className={cn(
                            "flex flex-1 items-center gap-1.5 rounded-md px-2 py-1 text-[12px] transition",
                            isSelected
                                ? "bg-accent/10 text-accent"
                                : "text-muted-foreground hover:bg-sidebar/40 hover:text-foreground",
                            isDisabled && "opacity-50 cursor-not-allowed"
                        )}
                    >
                        {/* Expand/collapse indicator */}
                        {isDir ? (
                            loading ? (
                                <Loader2 className="size-3 shrink-0 animate-spin text-muted-foreground/50" />
                            ) : (
                                <ChevronRight
                                    className={cn(
                                        "size-3 shrink-0 text-muted-foreground/50 transition-transform",
                                        isOpen && "rotate-90"
                                    )}
                                />
                            )
                        ) : (
                            <span className="w-3 shrink-0" />
                        )}

                        {/* Icon: custom > type-based default */}
                        {node.icon ? (
                            <span className="shrink-0">{node.icon}</span>
                        ) : isDir ? (
                            isOpen ? (
                                <FolderOpen className="size-3.5 shrink-0 text-muted-foreground/60" />
                            ) : (
                                <Folder className="size-3.5 shrink-0 text-muted-foreground/60" />
                            )
                        ) : (
                            <TreeFileIcon name={node.name} />
                        )}

                        <span className="truncate">{node.name}</span>
                    </button>
                </CollapsibleTrigger>
            </div>

            {/* Children (animated by Radix Collapsible) */}
            {isDir && children && children.length > 0 && (
                <CollapsibleContent>
                    {children.map((child) => (
                        <TreeNode
                            key={child.path || child.name}
                            node={child}
                            depth={depth + 1}
                            expandedPaths={expandedPaths}
                            selectedPath={selectedPath}
                            onSelect={onSelect}
                            onToggle={onToggle}
                            loadData={loadData}
                            checkable={checkable}
                            checkedPaths={checkedPaths}
                            onCheck={onCheck}
                        />
                    ))}
                </CollapsibleContent>
            )}
        </Collapsible>
    );
}

// ─── File icon by extension ─────────────────────────────────────────────────

export function TreeFileIcon({name}) {
    const ext = name.split(".").pop()?.toLowerCase();
    if (ext === "md")
        return <FileText className="size-3.5 shrink-0 text-muted-foreground/60" />;
    if (["py", "js", "jsx", "ts", "tsx", "sh", "json", "yaml", "yml", "css"].includes(ext))
        return <FileCode className="size-3.5 shrink-0 text-muted-foreground/50" />;
    return <File className="size-3.5 shrink-0 text-muted-foreground/40" />;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function collectDirs(node, dirs) {
    if (node.type === "dir") {
        dirs.add(node.path);
        for (const child of node.children || []) collectDirs(child, dirs);
    }
}

function walkDescendants(node, fn) {
    for (const child of node.children || []) {
        fn(child);
        walkDescendants(child, fn);
    }
}
