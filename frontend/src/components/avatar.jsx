import {useState} from "react";
import {observer} from "mobx-react-lite";

import {useStore} from "@/hooks/use-store.jsx";
import {cn} from "@/lib/utils";

/**
 * Avatar components — backed by a BUNDLED set of 50 DiceBear "adventurer"
 * SVG presets served offline from /avatar-presets (no network call).
 *
 * Resolution order for an agent:
 *   1. local saved avatar → /agent-assets/{name}/avatar.svg  (preferred)
 *   2. on error → a deterministic preset from /avatar-presets/XX.svg (fallback)
 *
 * The same seed always maps to the same preset, so an identity keeps a
 * stable face even without a saved local avatar. Background is transparent
 * so the avatar blends onto dark surfaces; a subtle ring separates it.
 *
 * Seed mapping (drives which preset/fallback):
 *   - root / default session → its session id (each chat gets a unique face)
 *   - subagent session       → its role name ("Researcher" / "Coder" / ...)
 *   - team session           → its member role seeds (overlapped avatars)
 */

// Number of bundled presets (backend/seed/avatars/01.svg .. NN.svg). Kept in
// sync with scripts/gen_avatar_presets.py --count (default 50).
const PRESET_COUNT = 50;

/**
 * Map any seed to one of the bundled preset SVGs (offline fallback).
 * Same seed → same preset. Mirrors the backend hash in agent_loader.
 */
function presetAvatarUrl(seed) {
    const s = seed || "default";
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    const id = String((h % PRESET_COUNT) + 1).padStart(2, "0");
    return `/avatar-presets/${id}.svg`;
}

/**
 * Build the local avatar URL for an agent (saved avatar.svg), WITHOUT any
 * cache-busting query. Cache invalidation is handled centrally inside the
 * Avatar component via agentStore.avatarReloadSignal, so callers never need
 * to thread a version through.
 * @param {string} agentName
 * Returns null if agentName is falsy or not a real agent name (e.g. "user-face").
 */
const NON_AGENT_SEEDS = new Set(["user-face", "team", "unknown", "default", "main"]);

export function localAvatarUrl(agentName) {
    if (!agentName || NON_AGENT_SEEDS.has(agentName)) return null;
    return `/agent-assets/${encodeURIComponent(agentName)}/avatar.svg`;
}

/**
 * A single avatar. Subscribes to agentStore.avatarReloadSignal so that when
 * ANY agent's avatar is updated, this <img> re-fetches the (same-URL) SVG
 * instead of serving the stale in-memory copy. Callers pass only `seed` —
 * no version plumbing needed.
 * @param {string} seed  stable identity (agent name) — used for preset fallback
 * @param {number} [size=36] px
 * @param {string} [src]  optional explicit image URL (overrides local lookup)
 */
export const Avatar = observer(function Avatar({seed, size = 36, className, src}) {
    const {agentStore} = useStore();
    const signal = agentStore?.avatarReloadSignal ?? 0;
    const [useFallback, setUseFallback] = useState(false);
    // Append ?v=<signal> to bust the browser cache when an avatar changes.
    // signal changes → URL changes → <img> re-fetches.
    const localSrc = src || localAvatarUrl(seed);
    const localSrcBusted = localSrc ? `${localSrc}?v=${signal}` : null;
    const imgSrc = (localSrcBusted && !useFallback) ? localSrcBusted : presetAvatarUrl(seed);

    return (
        <img
            src={imgSrc}
            alt=""
            width={size}
            height={size}
            loading="lazy"
            onError={() => {
                if (!useFallback && localSrcBusted) setUseFallback(true);
            }}
            className={cn(
                "shrink-0 rounded-full bg-card/60 object-cover ring-1 ring-border",
                className
            )}
            style={{width: size, height: size}}
        />
    );
});

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
export function TeamAvatar({seeds, size = 36}) {
    const list = (seeds && seeds.length ? seeds : ["team"]).slice(0, 4);
    const mini = Math.round(size * 0.42);

    return (
        <div
            className="relative flex shrink-0 items-center justify-center rounded-xl bg-sidebar ring-1 ring-border"
            style={{width: size, height: size}}
        >
            <div
                className="grid place-items-center"
                style={{
                    gridTemplateColumns: "1fr 1fr",
                    gap: Math.max(1, size * 0.04),
                }}
            >
                {list.slice(0, 4).map((seed, i) => (
                    <MiniAvatar key={i} seed={seed} size={mini}/>
                ))}
            </div>
        </div>
    );
}

/** A mini avatar inside TeamAvatar — supports local SVG + preset fallback. */
const MiniAvatar = observer(function MiniAvatar({seed, size}) {
    const {agentStore} = useStore();
    const signal = agentStore?.avatarReloadSignal ?? 0;
    const [useFallback, setUseFallback] = useState(false);
    const localSrc = localAvatarUrl(seed);
    const localSrcBusted = localSrc ? `${localSrc}?v=${signal}` : null;
    const imgSrc = (localSrcBusted && !useFallback) ? localSrcBusted : presetAvatarUrl(seed);
    return (
        <img
            src={imgSrc}
            alt=""
            width={size}
            height={size}
            loading="lazy"
            onError={() => {
                if (!useFallback && localSrcBusted) setUseFallback(true);
            }}
            className="rounded-full bg-card object-cover ring-1 ring-card"
            style={{width: size, height: size}}
        />
    );
});

/**
 * Topic avatar: renders based on the topic's agent roster.
 * - 1 agent → single Avatar
 * - 2+ agents → TeamAvatar (up to 4 mini faces)
 * @param {string[]} agents  agent names in this topic
 * @param {number} [size=36]
 */
export function TopicAvatar({topic, size = 36}) {
    if (topic.kind === "team") {
        return <TeamAvatar seeds={topic.agents} size={size}/>;
    } else {
        return <Avatar seed={topic.agents[0]} size={size}/>;
    }
}
