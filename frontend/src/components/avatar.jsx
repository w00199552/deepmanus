import { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Avatar components — DiceBear "adventurer" style, zero-dependency via HTTP API.
 *
 * The same seed always renders the same face, so a session keeps one stable
 * identity. Background is transparent so the avatar blends onto our dark
 * surfaces; a subtle ring separates it from the canvas.
 *
 *   https://api.dicebear.com/9.x/adventurer/svg?seed=<seed>&backgroundColor=transparent
 *
 * Seed mapping (drives the face):
 *   - root / default session → its session id (each chat gets a unique face)
 *   - subagent session       → its role name ("Researcher" / "Coder" / ...)
 *   - team session           → its member role seeds (overlapped avatars)
 */

const API = "https://api.dicebear.com/9.x/adventurer/svg";

// Light/tan skin tones only (the rest of the adventurer palette skewed too
// dark). Deterministically pick one per seed so a face keeps a stable tone.
const SKIN_TONES = ["ffdfba", "f5d0b0"];

function skinForSeed(seed) {
    // simple deterministic hash → pick a skin tone (same seed = same tone)
    let h = 0;
    for (let i = 0; i < seed.length; i++)
        h = (h * 31 + seed.charCodeAt(i)) >>> 0;
    return SKIN_TONES[h % SKIN_TONES.length];
}

function avatarUrl(seed) {
    const s = seed || "default";
    const skin = skinForSeed(s);
    // transparent bg + radius so it sits cleanly on dark surfaces; skinColor
    // forces variety the default palette wouldn't give us.
    return `${API}?seed=${encodeURIComponent(s)}&backgroundColor=transparent&radius=50&skinColor=${skin}`;
}

/**
 * Build the local avatar URL for an agent (saved avatar.svg).
 * @param {string} agentName
 * @param {number} [version]  cache-busting version (bump to force reload)
 * Returns null if agentName is falsy or not a real agent name (e.g. "user-face").
 */
const NON_AGENT_SEEDS = new Set(["user-face", "team", "unknown", "default", "main"]);
export function localAvatarUrl(agentName, version) {
    if (!agentName || NON_AGENT_SEEDS.has(agentName)) return null;
    const base = `/agent-assets/${encodeURIComponent(agentName)}/avatar.svg`;
    return version ? `${base}?v=${version}` : base;
}

/**
 * A single avatar.
 * @param {string} seed  stable identity (agent name) — used for DiceBear fallback
 * @param {number} [size=36] px
 * @param {string} [src]  optional explicit image URL (overrides local lookup)
 * @param {number} [version]  cache-busting version for local avatar reload
 */
export function Avatar({ seed, size = 36, className, src, version }) {
    const [useFallback, setUseFallback] = useState(false);
    const localSrc = src || localAvatarUrl(seed, version);
    const imgSrc = (localSrc && !useFallback) ? localSrc : avatarUrl(seed);

    return (
        <img
            src={imgSrc}
            alt=""
            width={size}
            height={size}
            loading="lazy"
            onError={() => {
                if (!useFallback && localSrc) setUseFallback(true);
            }}
            className={cn(
                "shrink-0 rounded-full bg-card/60 object-cover ring-1 ring-border",
                className
            )}
            style={{ width: size, height: size }}
        />
    );
}

/**
 * A team avatar: a single badge containing mini member faces, communicating
 * "a group of specialists" in one icon (rather than overlapping heads).
 *
 * Layout: a rounded container (accent-tinted) holding the members' mini
 * avatars in a 2-column grid. The TeamLeader is larger and centered; the
 * others sit around it. Falls back to a "team" glyph if no members.
 *
 * @param {string[]} seeds  member identity seeds (1-4)
 * @param {number}   [size=36] px of the whole badge
 */
export function TeamAvatar({ seeds, size = 36 }) {
    const list = (seeds && seeds.length ? seeds : ["team"]).slice(0, 4);
    const mini = Math.round(size * 0.42); // mini avatar size inside the badge

    return (
        <div
            className="relative flex shrink-0 items-center justify-center rounded-xl bg-sidebar ring-1 ring-border"
            style={{ width: size, height: size }}
        >
            {/* up to 4 mini faces in a 2x2 grid inside the badge */}
            <div
                className="grid place-items-center"
                style={{
                    gridTemplateColumns: "1fr 1fr",
                    gap: Math.max(1, size * 0.04),
                }}
            >
                {list.slice(0, 4).map((seed, i) => (
                    <img
                        key={i}
                        src={avatarUrl(seed)}
                        alt=""
                        width={mini}
                        height={mini}
                        loading="lazy"
                        className="rounded-full bg-card object-cover ring-1 ring-card"
                        style={{ width: mini, height: mini }}
                    />
                ))}
            </div>
        </div>
    );
}

/**
 * Pick the right avatar for a session based on its kind + role data.
 * Returns the component to render.
 *
 * @param {object} session  the session row (kind, id, name, metadata)
 * @param {number} [size]
 */
export function SessionAvatar({ session, size = 36 }) {
    if (session.kind === "team") {
        // members: prefer metadata.members if present, else a sensible default roster
        const members = session.metadata?.members || [
            "TeamLeader",
            "Researcher",
            "Coder",
        ];
        return <TeamAvatar seeds={members} size={size} />;
    }
    // Seed by agent name (stable identity): same agent = same face everywhere
    // (topicList, message stream, agents page). Accept both `name` (session)
    // and `agent_name` (topic) since the frontend mixes both object shapes.
    const seed = session.name || session.agent_name || session.id || "unknown";
    return <Avatar seed={seed} size={size} />;
}
