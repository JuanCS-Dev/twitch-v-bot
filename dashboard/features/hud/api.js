export async function fetchHudMessages(since = 0) {
    const res = await fetch(`/api/hud/messages?since=${since}`);
    if (!res.ok) throw new Error("Falha ao buscar HUD messages");
    return res.json();
}
