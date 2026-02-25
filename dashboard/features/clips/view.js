// Template string seguro para renderizar cartões de clips
// Usa escapeHtml para evitar XSS
function escapeHtml(str) {
    if (!str) return "";
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

export function renderClipCard(job) {
    const createdTime = new Date(job.created_at).toLocaleTimeString();
    const status = job.status || "queued";

    // Links condicionais baseados no status
    let actionsHtml = '';
    if (status === 'ready' && job.clip_url) {
        actionsHtml += `<a href="${escapeHtml(job.clip_url)}" target="_blank" class="btn btn-primary btn-sm">Abrir Clip</a>`;
        if (job.download_url) {
            actionsHtml += `<a href="${escapeHtml(job.download_url)}" target="_blank" class="btn btn-success btn-sm">Download</a>`;
        }
        actionsHtml += `<a href="${escapeHtml(job.edit_url)}" target="_blank" class="btn btn-secondary btn-sm">Editar</a>`;
    } else if (status === 'creating' || status === 'polling') {
        if (job.edit_url) {
             actionsHtml += `<a href="${escapeHtml(job.edit_url)}" target="_blank" class="btn btn-secondary btn-sm">Editar (WIP)</a>`;
        }
    } else if (status === 'failed') {
        // Retry manual será implementado futuramente se houver endpoint para isso
        // Por enquanto apenas exibe erro
    }

    return `
    <article class="clip-card" data-status="${escapeHtml(status)}" data-id="${escapeHtml(job.job_id)}">
        <div class="clip-header">
            <span class="clip-status-indicator"></span>
            <span class="clip-id-label">#${escapeHtml(job.action_id.split('_').pop())}</span>
            <time class="clip-time">${createdTime}</time>
        </div>
        <div class="clip-body">
            <h4 class="clip-title">${escapeHtml(job.title || "Sem título")}</h4>
            <div class="clip-meta">
                <span class="meta-item mode">${escapeHtml(job.mode)}</span>
                <span class="meta-item broadcaster">${escapeHtml(job.broadcaster_id)}</span>
            </div>
            ${job.error ? `<div class="clip-error">${escapeHtml(job.error)}</div>` : ''}
        </div>
        <div class="clip-actions">
            ${actionsHtml}
        </div>
    </article>
    `;
}

export function getClipsElements() {
    return {
        container: document.getElementById("clipsList"),
        loadingSkeleton: document.getElementById("clipsSkeleton"),
        section: document.getElementById("clipsSection"),
    };
}
