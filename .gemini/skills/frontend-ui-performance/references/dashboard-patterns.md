# Dashboard & Real-Time UI Patterns

> Context: Internal operator dashboards. The user is NOT a casual visitor —
> they're an operator who needs information density, fast status reads,
> and reliable action feedback. Design for that person.

---

## The Operator Dashboard Contract

An operator dashboard must satisfy:
1. **Information at a glance** — status readable in < 300ms without reading text
2. **Zero ambiguity** — error states show exact error, not "something went wrong"
3. **Safe actions** — destructive actions require confirmation
4. **Self-serviceable** — operator resolves 100% of cases without opening server logs
5. **Reliable feedback** — every action has explicit success/failure feedback

---

## Polling Architecture

### Adaptive Polling with Backoff

```js
class Poller {
  #timerId = null;
  #running = false;
  #consecutiveErrors = 0;

  constructor(fetchFn, {
    baseInterval = 3000,
    maxInterval = 30000,
    backoffFactor = 1.5,
    onData,
    onError
  } = {}) {
    this.#fetchFn = fetchFn;
    this.#baseInterval = baseInterval;
    this.#maxInterval = maxInterval;
    this.#backoffFactor = backoffFactor;
    this.#onData = onData;
    this.#onError = onError;

    // Pause when tab hidden — saves resources
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.#pause();
      } else {
        this.#resume();
      }
    });
  }

  get #currentInterval() {
    if (this.#consecutiveErrors === 0) return this.#baseInterval;
    return Math.min(
      this.#baseInterval * (this.#backoffFactor ** this.#consecutiveErrors),
      this.#maxInterval
    );
  }

  start() {
    this.#running = true;
    this.#tick();
    return this;
  }

  stop() {
    this.#running = false;
    clearTimeout(this.#timerId);
  }

  // Force immediate poll (e.g., after a user action)
  async poll() {
    clearTimeout(this.#timerId);
    await this.#tick();
  }

  #pause() { clearTimeout(this.#timerId); }

  #resume() {
    if (this.#running) this.#tick();
  }

  async #tick() {
    try {
      const data = await this.#fetchFn();
      this.#consecutiveErrors = 0;
      this.#onData?.(data);
    } catch(err) {
      this.#consecutiveErrors++;
      this.#onError?.(err);
    } finally {
      if (this.#running && !document.hidden) {
        this.#timerId = setTimeout(() => this.#tick(), this.#currentInterval);
      }
    }
  }
}

// Usage
const poller = new Poller(
  () => fetch('/api/clip-jobs').then(r => r.json()),
  {
    baseInterval: 3000,
    onData: data => clipStore.set({ jobs: data.jobs, status: 'ok' }),
    onError: err => clipStore.set({ status: 'error', error: err.message })
  }
).start();
```

---

## Status Lifecycle Display

### State Machine for Clip Jobs

```
queued → creating → polling → ready
                           ↘ failed

Any state can go to → failed
failed → retry → creating (manual, limited)
```

### Status Badge Component

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--primitive-radius-full);
  font-size: var(--primitive-text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

/* Status variants */
.badge--queued   { background: rgba(59, 130, 246, 0.15); color: #93c5fd; }
.badge--creating { background: rgba(245, 158, 11, 0.15); color: #fcd34d; }
.badge--polling  { background: rgba(245, 158, 11, 0.15); color: #fcd34d; }
.badge--ready    { background: rgba(34, 197, 94, 0.15);  color: #86efac; }
.badge--failed   { background: rgba(239, 68, 68, 0.15);  color: #fca5a5; }

/* Pulsing dot for in-progress states */
.badge--creating::before,
.badge--polling::before {
  content: '';
  display: block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.4; transform: scale(0.8); }
}

@media (prefers-reduced-motion: reduce) {
  .badge--creating::before,
  .badge--polling::before {
    animation: none;
  }
}
```

---

## Error Display — Never Hide The Real Error

```js
// ❌ WRONG — useless to the operator
showError('Falha ao criar clip');

// ✅ CORRECT — operator can act on this
function showJobError(job) {
  const messages = {
    '400': 'Parâmetro inválido ou canal não clippable.',
    '401': 'Token inválido ou escopo faltando. Reconecte a conta.',
    '403': 'Clips desabilitados ou usuário banido no canal.',
    '404': 'Canal não está ao vivo.',
    '429': `Rate limit atingido. Próxima tentativa em ${job.retry_after}s.`,
    'TIMEOUT': 'Clip não confirmado em 15s. Verifique em Get Clips.',
  };

  const userMessage = messages[job.error_code] || job.error_detail || 'Erro desconhecido';

  return `
    <div class="error-block" role="alert">
      <span class="error-icon" aria-hidden="true">⚠</span>
      <div class="error-content">
        <p class="error-message">${escapeHtml(userMessage)}</p>
        <details class="error-technical">
          <summary class="text-xs text-muted">Detalhes técnicos</summary>
          <code class="text-xs">${escapeHtml(job.error_code)} · ${escapeHtml(job.error_detail || '')}</code>
          <code class="text-xs">action_id: ${escapeHtml(job.action_id)}</code>
          <code class="text-xs">job_id: ${escapeHtml(job.id)}</code>
        </details>
      </div>
    </div>
  `;
}
```

---

## Skeleton Loading System

```js
// Generate skeleton placeholder that matches the final card height
function renderSkeletonCard() {
  return `
    <article class="clip-card clip-card--skeleton" aria-hidden="true">
      <div class="skeleton" style="width: 60px; height: 18px;"></div>
      <div class="skeleton" style="width: 80%; height: 20px; margin-top: 8px;"></div>
      <div class="skeleton" style="width: 40%; height: 14px; margin-top: 4px;"></div>
      <div style="display:flex; gap: 8px; margin-top: 12px;">
        <div class="skeleton" style="width: 80px; height: 32px;"></div>
        <div class="skeleton" style="width: 80px; height: 32px;"></div>
      </div>
    </article>
  `;
}

// Show skeletons on initial load
function initLoadingState(container, count = 3) {
  container.innerHTML = Array(count).fill(renderSkeletonCard()).join('');
  // Announce to screen readers
  container.setAttribute('aria-busy', 'true');
  container.setAttribute('aria-label', 'Carregando clips…');
}

// Replace with real data
function replaceWithData(container, jobs) {
  container.innerHTML = jobs.length > 0
    ? jobs.map(renderCard).join('')
    : renderEmptyState();
  container.removeAttribute('aria-busy');
  container.setAttribute('aria-label', `${jobs.length} clips`);
}
```

---

## Empty State Design

Empty states are UI, not afterthoughts. Always design them.

```js
function renderEmptyState() {
  return `
    <div class="empty-state" role="status">
      <svg class="empty-state__icon" aria-hidden="true" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M15 10l4.553-2.069A1 1 0 0121 8.845v6.31a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z"/>
      </svg>
      <h3 class="empty-state__title">Nenhum clip em fila</h3>
      <p class="empty-state__description text-secondary">
        O agente ainda não detectou nenhum momento clippável.<br>
        Os candidatos aparecerão aqui automaticamente.
      </p>
    </div>
  `;
}
```

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-12) var(--primitive-space-6);
  text-align: center;
  color: var(--color-text-secondary);
}

.empty-state__icon {
  opacity: 0.4;
  color: var(--color-text-muted);
}

.empty-state__title {
  font-size: var(--primitive-text-lg);
  font-weight: 600;
  color: var(--color-text-secondary);
}
```

---

## Notification / Toast System

```js
class Toast {
  static #container;

  static #getContainer() {
    if (!this.#container) {
      this.#container = document.createElement('div');
      this.#container.className = 'toast-container';
      this.#container.setAttribute('role', 'log');
      this.#container.setAttribute('aria-live', 'polite');
      this.#container.setAttribute('aria-label', 'Notificações');
      document.body.appendChild(this.#container);
    }
    return this.#container;
  }

  static show(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;

    const container = this.#getContainer();
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
      requestAnimationFrame(() => toast.classList.add('toast--visible'));
    });

    // Auto-remove
    const remove = () => {
      toast.classList.remove('toast--visible');
      toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    };

    setTimeout(remove, duration);
    toast.addEventListener('click', remove); // click to dismiss

    return remove; // allow manual dismiss
  }

  static success(msg) { return this.show(msg, 'success'); }
  static error(msg)   { return this.show(msg, 'error', 8000); }
  static warning(msg) { return this.show(msg, 'warning'); }
}
```

```css
.toast-container {
  position: fixed;
  bottom: var(--primitive-space-4);
  right: var(--primitive-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
  z-index: 9999;
  pointer-events: none;
}

.toast {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  border-radius: var(--primitive-radius-md);
  font-size: var(--primitive-text-sm);
  font-weight: 500;
  max-width: 360px;
  pointer-events: auto;
  cursor: pointer;
  /* Start invisible, off-screen */
  opacity: 0;
  transform: translateX(8px);
  transition: opacity var(--transition-ui), transform var(--transition-ui);
  border-left: 3px solid currentColor;
}

.toast--visible {
  opacity: 1;
  transform: translateX(0);
}

.toast--success { background: #1a2d1e; color: #86efac; }
.toast--error   { background: #2d1a1a; color: #fca5a5; }
.toast--warning { background: #2d2a1a; color: #fcd34d; }
.toast--info    { background: #1a1e2d; color: #93c5fd; }
```

---

## Confirmation Dialog (native, accessible)

Use the native `<dialog>` element — no library needed, full a11y built-in.

```js
function confirm({ title, message, confirmLabel = 'Confirmar', danger = false }) {
  return new Promise(resolve => {
    const dialog = document.createElement('dialog');
    dialog.className = 'confirm-dialog';
    dialog.innerHTML = `
      <h2 class="confirm-dialog__title">${escapeHtml(title)}</h2>
      <p class="confirm-dialog__message">${escapeHtml(message)}</p>
      <div class="confirm-dialog__actions">
        <button class="btn btn--ghost" data-action="cancel">Cancelar</button>
        <button class="btn ${danger ? 'btn--danger' : 'btn--primary'}" data-action="confirm">
          ${escapeHtml(confirmLabel)}
        </button>
      </div>
    `;

    document.body.appendChild(dialog);
    dialog.showModal();

    dialog.addEventListener('click', e => {
      const action = e.target.closest('[data-action]')?.dataset.action;
      if (action === 'confirm') { dialog.close(); resolve(true); }
      if (action === 'cancel')  { dialog.close(); resolve(false); }
    });

    dialog.addEventListener('close', () => {
      dialog.remove();
      resolve(false);
    });
  });
}

// Usage
const ok = await confirm({
  title: 'Tentar novamente?',
  message: `Recriar clip "${job.title}"? Isso consumirá uma tentativa.`,
  confirmLabel: 'Sim, tentar',
  danger: false
});
if (ok) retryJob(job.id);
```

---

## Accessibility Checklist for Dashboards

```js
// Announce dynamic updates to screen readers
function announceUpdate(message) {
  const el = document.getElementById('sr-announcer') || (() => {
    const div = document.createElement('div');
    div.id = 'sr-announcer';
    div.setAttribute('role', 'status');
    div.setAttribute('aria-live', 'polite');
    div.setAttribute('aria-atomic', 'true');
    div.className = 'sr-only';
    document.body.appendChild(div);
    return div;
  })();

  // Clear then set (forces re-announcement)
  el.textContent = '';
  requestAnimationFrame(() => { el.textContent = message; });
}

// Usage
announceUpdate(`Clip "${job.title}" criado com sucesso`);
announceUpdate(`Erro ao criar clip: ${job.error_code}`);
```

```css
/* Screen-reader only utility */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

---

## Complete Dashboard Init Pattern

```js
// dashboard/features/clips/index.js

const clipStore = new Store({
  jobs: [],
  status: 'loading',
  error: null,
  lastUpdated: null
});

// Bind store to DOM
clipStore.subscribe('jobs', ({ jobs, status }) => {
  const container = document.querySelector('.clips-grid');
  if (!container) return;

  if (status === 'loading') {
    initLoadingState(container);
    return;
  }

  reconcileList(container, jobs, j => j.id, renderCard);
  document.querySelector('.clips-count').textContent = jobs.length;
  announceUpdate(`${jobs.length} clips atualizados`);
});

clipStore.subscribe('error', ({ error }) => {
  if (error) Toast.error(`Falha ao buscar clips: ${error}`);
});

// Start polling
const poller = new Poller(
  async () => {
    const r = await fetch('/api/clip-jobs');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
  {
    baseInterval: 3000,
    onData: data => clipStore.set({ jobs: data.jobs, status: 'ok', lastUpdated: Date.now() }),
    onError: err => clipStore.set({ status: 'error', error: err.message })
  }
).start();

// Event delegation for all card actions
document.querySelector('.clips-grid').addEventListener('click', async e => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;

  const { action, id, url } = btn.dataset;

  if (action === 'copy') {
    await copyToClipboard(url, btn);
    return;
  }

  if (action === 'retry') {
    const job = clipStore.get('jobs').find(j => j.id === id);
    const ok = await confirm({
      title: 'Tentar novamente?',
      message: `Recriar "${job?.title || 'este clip'}"?`
    });
    if (!ok) return;

    // Optimistic update
    updateJobStatus(id, 'creating');

    try {
      await fetch(`/api/clip-jobs/${id}/retry`, { method: 'POST' });
      await poller.poll(); // force immediate refresh
    } catch(err) {
      updateJobStatus(id, 'failed');
      Toast.error(`Retry falhou: ${err.message}`);
    }
  }
});

function updateJobStatus(id, status) {
  const jobs = clipStore.get('jobs').map(j =>
    j.id === id ? { ...j, status } : j
  );
  clipStore.set({ jobs });
}
```
