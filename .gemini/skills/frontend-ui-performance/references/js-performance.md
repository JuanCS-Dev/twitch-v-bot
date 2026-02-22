# JavaScript Performance — Deep Reference

> Premise: The browser's main thread is sacred. Every millisecond you block it
> is a millisecond the user can't scroll, click, or see anything update.

---

## The Main Thread Budget

At 60fps, each frame has **16.67ms** to complete:
- JS execution
- Style recalculation
- Layout
- Paint
- Composite

**Rule**: Keep any single task under 50ms. If it's longer, it's a "long task" and will hurt INP.

---

## Memory Management

### Common Memory Leaks in UIs

```js
// ❌ LEAK: Event listener never removed
function mountCard(el, data) {
  el.addEventListener('click', handler); // handler closes over data
  // If el is removed from DOM, listener still holds reference to data
}

// ✅ CORRECT: Clean up on teardown
function mountCard(el, data) {
  const controller = new AbortController();
  el.addEventListener('click', handler, { signal: controller.signal });
  return () => controller.abort(); // call this to clean up
}
```

```js
// ❌ LEAK: Interval not cleared
class Dashboard {
  init() {
    setInterval(this.poll.bind(this), 3000);
    // If Dashboard is destroyed, interval continues forever
  }
}

// ✅ CORRECT
class Dashboard {
  #intervalId;
  init() { this.#intervalId = setInterval(this.poll.bind(this), 3000); }
  destroy() { clearInterval(this.#intervalId); }
}
```

```js
// ❌ LEAK: Observer not disconnected
const obs = new MutationObserver(cb);
obs.observe(document.body, { childList: true });
// Never disconnected

// ✅ CORRECT
const obs = new MutationObserver(cb);
obs.observe(target, { childList: true });
// On teardown:
obs.disconnect();
```

---

## Batch DOM Updates

### DocumentFragment for bulk inserts

```js
// ❌ Causes N layout reflows
items.forEach(item => {
  container.innerHTML += renderItem(item); // each += reads AND writes
});

// ✅ One reflow
function renderList(container, items) {
  const html = items.map(renderItem).join('');
  container.innerHTML = html; // single write
}

// ✅ Even better for append-only (preserves existing DOM)
function appendItems(container, newItems) {
  const fragment = document.createDocumentFragment();
  newItems.forEach(item => {
    const el = document.createElement('article');
    el.innerHTML = renderItem(item);
    fragment.appendChild(el.firstElementChild);
  });
  container.appendChild(fragment); // single reflow
}
```

---

## Efficient Reconciliation (Vanilla JS)

When you need to update a list without replacing everything:

```js
/**
 * Key-based DOM reconciliation
 * Preserves DOM nodes for items that haven't changed
 * Only updates nodes that differ
 */
function reconcileList(container, newItems, keyFn, renderFn) {
  const existingMap = new Map();

  // Index existing nodes by key
  container.querySelectorAll('[data-key]').forEach(el => {
    existingMap.set(el.dataset.key, el);
  });

  const fragment = document.createDocumentFragment();

  newItems.forEach(item => {
    const key = String(keyFn(item));
    let el = existingMap.get(key);

    if (!el) {
      // New item — create DOM node
      el = document.createElement('article');
      el.dataset.key = key;
      el.innerHTML = renderFn(item);
    } else {
      // Existing item — update only changed attrs
      updateNode(el, item);
      existingMap.delete(key); // mark as used
    }

    fragment.appendChild(el);
  });

  // Remove nodes no longer in list
  existingMap.forEach(el => el.remove());

  container.appendChild(fragment);
}

// Update only what changed (cheap attr writes > innerHTML re-parse)
function updateNode(el, job) {
  if (el.dataset.status !== job.status) {
    el.dataset.status = job.status;
    el.querySelector('.clip-status').textContent = job.status;
  }
}
```

---

## Debounce & Throttle

```js
// Debounce: fire AFTER the user stops (search input, resize)
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// Throttle: fire AT MOST every N ms (scroll, mousemove)
function throttle(fn, ms) {
  let last = 0;
  return (...args) => {
    const now = Date.now();
    if (now - last >= ms) {
      last = now;
      fn(...args);
    }
  };
}

// requestAnimationFrame throttle (for visual updates)
function rafThrottle(fn) {
  let rafId;
  return (...args) => {
    cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => fn(...args));
  };
}
```

---

## Web Workers — Offload Heavy Computation

Use when you have computation that takes > 20ms (parsing, sorting, filtering large datasets).

```js
// main.js
const worker = new Worker('/workers/clip-processor.js');

worker.postMessage({ type: 'FILTER', jobs: allJobs, status: 'ready' });

worker.addEventListener('message', e => {
  if (e.data.type === 'FILTERED') {
    renderList(container, e.data.jobs);
  }
});

// /workers/clip-processor.js
self.addEventListener('message', e => {
  if (e.data.type === 'FILTER') {
    const filtered = e.data.jobs.filter(j => j.status === e.data.status);
    self.postMessage({ type: 'FILTERED', jobs: filtered });
  }
});
```

---

## Scheduler API — Yield to the Main Thread

When you must do long work on the main thread, yield periodically:

```js
// Modern browsers
async function processLargeList(items) {
  const results = [];

  for (let i = 0; i < items.length; i++) {
    results.push(processItem(items[i]));

    // Yield every 50 items so browser can handle user input
    if (i % 50 === 0) {
      if ('scheduler' in window && 'yield' in scheduler) {
        await scheduler.yield(); // preferred — preserves task priority
      } else {
        await new Promise(resolve => setTimeout(resolve, 0)); // fallback
      }
    }
  }
  return results;
}
```

---

## State Management — Minimal, Explicit

### Reactive Store Pattern (zero dependencies)

```js
/**
 * Observable store — pub/sub pattern
 * No Proxy, no magic, no framework
 */
class Store {
  #state;
  #subscribers = new Map(); // key -> Set<fn>

  constructor(initialState) {
    this.#state = Object.freeze({ ...initialState });
  }

  get(key) {
    return key ? this.#state[key] : this.#state;
  }

  set(patch) {
    const prev = this.#state;
    this.#state = Object.freeze({ ...prev, ...patch });

    // Notify subscribers of changed keys only
    Object.keys(patch).forEach(key => {
      if (prev[key] !== this.#state[key]) {
        this.#notify(key);
      }
    });
    this.#notify('*'); // catch-all
  }

  #notify(key) {
    this.#subscribers.get(key)?.forEach(fn => fn(this.#state));
  }

  subscribe(key, fn) {
    if (!this.#subscribers.has(key)) {
      this.#subscribers.set(key, new Set());
    }
    this.#subscribers.get(key).add(fn);
    return () => this.#subscribers.get(key).delete(fn); // unsubscribe
  }
}

// Usage
const clipStore = new Store({
  jobs: [],
  status: 'idle',
  error: null
});

// Subscribe to specific key
const unsub = clipStore.subscribe('jobs', state => {
  renderJobList(state.jobs);
});

// Update
clipStore.set({ jobs: newJobs });

// Clean up (e.g. when component unmounts)
unsub();
```

---

## Template Literals — Safe, Fast Rendering

```js
// Safe HTML generation
const escapeHtml = (() => {
  const div = document.createElement('div');
  return str => {
    div.textContent = str;
    return div.innerHTML;
  };
})();

// Tagged template literal for safe HTML
function html(strings, ...values) {
  return strings.reduce((acc, str, i) => {
    const val = values[i - 1];
    const safe = typeof val === 'string' ? escapeHtml(val) : (val ?? '');
    return acc + safe + str;
  });
}

// Usage — values automatically escaped
function renderCard(job) {
  return html`
    <article class="clip-card" data-status="${job.status}" data-key="${job.id}">
      <header class="clip-card__header">
        <span class="badge badge--${job.status}">${job.status}</span>
        <h3 class="clip-card__title">${job.title || 'Sem título'}</h3>
      </header>
      <div class="clip-card__meta text-mono text-xs text-muted">
        ID: ${job.id} · Tentativas: ${job.attempts}
      </div>
      ${job.error ? html`<p class="clip-card__error text-sm">${job.error}</p>` : ''}
      <footer class="clip-card__actions">
        ${renderActions(job)}
      </footer>
    </article>
  `;
}

function renderActions(job) {
  if (job.status === 'ready') {
    return html`
      <a href="${job.clip_url}" target="_blank" rel="noopener" class="btn btn--primary btn--sm">
        Abrir clip
      </a>
      <a href="${job.edit_url}" target="_blank" rel="noopener" class="btn btn--ghost btn--sm">
        Editar
      </a>
      <button class="btn btn--ghost btn--sm" data-action="copy" data-url="${job.clip_url}">
        Copiar URL
      </button>
    `;
  }
  if (job.status === 'failed') {
    return html`
      <button class="btn btn--ghost btn--sm" data-action="retry" data-id="${job.id}">
        Tentar novamente
      </button>
      <span class="text-xs text-muted">${job.error_code || ''}</span>
    `;
  }
  // loading states
  return html`<span class="text-sm text-muted">Processando…</span>`;
}
```

---

## Clipboard API (modern, no hacks)

```js
async function copyToClipboard(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    // Visual feedback
    const original = btn.textContent;
    btn.textContent = '✓ Copiado';
    btn.disabled = true;
    setTimeout(() => {
      btn.textContent = original;
      btn.disabled = false;
    }, 2000);
  } catch {
    // Fallback for insecure contexts
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
}
```

---

## Performance Measurement

```js
// Mark and measure custom operations
performance.mark('render-start');
renderJobList(jobs);
performance.mark('render-end');
performance.measure('job-list-render', 'render-start', 'render-end');

const [entry] = performance.getEntriesByName('job-list-render');
if (entry.duration > 50) {
  console.warn(`Slow render: ${entry.duration.toFixed(1)}ms for ${jobs.length} jobs`);
}
```

---

## Intersection Observer — Lazy Load Anything

```js
// Lazy-load heavy content when it enters viewport
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      loadContent(entry.target);
      observer.unobserve(entry.target); // stop watching after load
    }
  });
}, {
  rootMargin: '100px', // start loading 100px before visible
  threshold: 0
});

document.querySelectorAll('[data-lazy]').forEach(el => observer.observe(el));
```
