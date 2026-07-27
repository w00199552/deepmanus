/**
 * Topic service — the ONLY place that talks to the /topics backend.
 * Views go through topic-store actions → these functions. Never call directly.
 */

/** List all topics (newest first), with latest session info merged in. */
export async function listTopics() {
    const res = await fetch("/topics");
    if (!res.ok) throw new Error(`listTopics: ${res.status}`);
    return res.json();
}

/** Delete a topic and all its data (sessions/checkpoints/whiteboard/mailbox). */
export async function deleteTopic(id) {
    const res = await fetch(`/topics/${encodeURIComponent(id)}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error(`deleteTopic: ${res.status}`);
    return res.json();
}
