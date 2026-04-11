// trialcat frontend — Phase 1 placeholder
// Just proves the static file pipeline works. Phase 4 will replace this
// with Leaflet map setup, filter wiring, and API calls.

(async function () {
    // Hit the health endpoint at load to prove the backend is reachable
    try {
        const res = await fetch("/health");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        console.info("[trialcat] health check OK:", data);
    } catch (err) {
        console.error("[trialcat] health check failed:", err);
    }
})();
