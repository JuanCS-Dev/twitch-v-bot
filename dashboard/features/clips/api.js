export async function fetchClipJobs() {
    const res = await fetch("./api/clip-jobs");
    if (!res.ok) throw new Error("Falha ao buscar clip jobs");
    return res.json();
}
