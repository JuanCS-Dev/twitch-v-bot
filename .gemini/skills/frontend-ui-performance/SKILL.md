---
name: frontend-ui-performance
description: >
  Expert-level frontend UI/UX development with performance as the primary success criterion.
  Use this skill whenever the user asks to build, design, or improve any frontend interface —
  dashboards, components, landing pages, admin panels, real-time UIs, or data displays.
  Trigger this skill when the user mentions HTML, CSS, JS, UI, UX, frontend, dashboard, components,
  design system, responsive, or any visual interface work. This skill applies regardless of stack:
  vanilla JS, Svelte, SolidJS, Lit, Web Components — it teaches you to CHOOSE and EXECUTE with
  quality. The single success criterion is: does it perform AND look good, with zero unnecessary
  dependencies?
---

# Frontend UI/UX — Performance-First Expert Skill

> **Doctrine**: A beautiful UI that is slow is a broken UI. An ugly UI that is fast is still a broken UI.
> Quality means BOTH. The goal is the intersection.

---

## 0. Before Writing Any Code — The Mandatory Stack Decision

**Never assume the stack. Always derive it from requirements.**

| Signal | Recommended Stack |
|--------|------------------|
| Dashboard, internal tool, no SEO | Vanilla JS + Web Components or Lit |
| Real-time data, frequent DOM updates | Svelte 5 or SolidJS (signal-based, no vDOM overhead) |
| Content site, blog, marketing | Astro (zero-JS by default, islands for interactivity) |
| Complex SPA with team > 3 | SvelteKit or SolidStart |
| Existing vanilla JS codebase | Extend vanilla — no migration tax |
| React already in project | Stay React — optimize it, don't rewrite |

**Hard rule**: Never install a framework to solve a problem that the platform already solves.
Check `references/stack-decision.md` for detailed decision matrix with benchmarks.

---

## 1. The Browser Rendering Pipeline — Know This Cold

Every performance decision traces back to understanding **what the browser actually does**:

```
JavaScript → Style → Layout → Paint → Composite
```

- **Layout (Reflow)**: Triggered by changes to geometry (width, height, position, margin, padding).
  This is the most expensive step. Avoid triggering it in loops.
- **Paint**: Triggered by visual changes (color, box-shadow, background). Expensive on complex elements.
- **Composite**: CSS transforms (`translate`, `scale`, `rotate`, `opacity`) only — runs on GPU thread.
  This is what you want for animations. Zero layout, zero paint.

**The golden rule of animations**: Only animate `transform` and `opacity`. Everything else causes layout thrash.

### Layout Thrash — The Silent Killer

```js
// ❌ KILLS performance — reads force sync layout, writes invalidate it
elements.forEach(el => {
  const h = el.offsetHeight;   // READ — forces sync layout
  el.style.height = h + 'px'; // WRITE — invalidates layout
});

// ✅ CORRECT — batch reads, then batch writes
const heights = elements.map(el => el.offsetHeight); // all reads
elements.forEach((el, i) => el.style.height = heights[i] + 'px'); // all writes
```

Use `requestAnimationFrame` to schedule visual updates:
```js
function scheduleUpdate(fn) {
  requestAnimationFrame(() => {
    // reads first
    const rect = el.getBoundingClientRect();
    // writes after
    requestAnimationFrame(() => fn(rect));
  });
}
```

For detailed JS performance patterns → `references/js-performance.md`

---

## 2. Core Web Vitals — The Performance Contract

These are non-negotiable targets. Know them, measure them, design for them.

| Metric | Good | Needs Work | Poor | What It Measures |
|--------|------|-----------|------|-----------------|
| **LCP** | ≤ 2.5s | 2.5–4s | > 4s | When largest content paints |
| **INP** | ≤ 200ms | 200–500ms | > 500ms | Interaction responsiveness |
| **CLS** | ≤ 0.1 | 0.1–0.25 | > 0.25 | Layout shift during load |

### LCP Optimization Checklist
- [ ] Preload the LCP resource: `<link rel="preload" href="..." as="image">`
- [ ] Inline critical CSS (`<style>` in `<head>` for above-the-fold)
- [ ] Defer non-critical CSS: `<link rel="stylesheet" media="print" onload="this.media='all'">`
- [ ] No render-blocking scripts above fold
- [ ] Images have explicit `width` and `height` attributes

### INP Optimization Checklist
- [ ] Event handlers complete in < 50ms (or yield to main thread)
- [ ] No long tasks (> 50ms) on main thread during interaction
- [ ] Use `scheduler.yield()` or `setTimeout(0)` to break up long work
- [ ] Debounce/throttle inputs (`input`, `scroll`, `resize`)
- [ ] Web Workers for heavy computation (parsing, sorting large datasets)

### CLS Prevention Checklist
- [ ] All images/video have explicit dimensions (or use `aspect-ratio` CSS)
- [ ] Reserve space for dynamically loaded content (skeleton loaders, min-height)
- [ ] Fonts: use `font-display: optional` or `font-display: swap` + FOUT mitigation
- [ ] Never inject content above existing content after load
- [ ] Ads/embeds have explicit size containers

---

## 3. CSS Architecture — Scalable Without a Framework

### Layer Model (use `@layer` — supported in all modern browsers)

```css
@layer reset, tokens, base, layout, components, utilities, overrides;
```

This gives you explicit cascade control. No specificity wars.

### Design Token System (CSS Custom Properties)

**Two-tier token architecture**:

```css
/* Tier 1: Primitive tokens (raw values — never use directly in components) */
:root {
  --color-blue-500: #3b82f6;
  --color-red-500: #ef4444;
  --color-green-500: #22c55e;
  --space-1: 4px;
  --space-2: 8px;
  --space-4: 16px;
  --radius-sm: 4px;
  --radius-md: 8px;
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --ease-out: cubic-bezier(0.25, 0, 0, 1);
}

/* Tier 2: Semantic tokens (what components use) */
:root {
  --color-status-success: var(--color-green-500);
  --color-status-error: var(--color-red-500);
  --color-status-pending: var(--color-blue-500);
  --color-bg-card: #1a1a2e;
  --color-text-primary: #e2e8f0;
  --color-text-muted: #94a3b8;
  --space-card-padding: var(--space-4);
  --transition-ui: var(--duration-fast) var(--ease-out);
}

/* Dark mode — no JS needed */
@media (prefers-color-scheme: dark) {
  :root { /* already dark, example only */ }
}
```

**Rule**: Components ONLY reference semantic tokens, never primitives.

### CSS Containment — Critical for Dashboard Performance

```css
/* Each card is an isolated rendering context */
.clip-card {
  contain: layout style paint; /* browser can skip reflow outside this box */
  /* or shorthand: */
  contain: content;
}

/* Offscreen items — don't render them at all */
.offscreen-section {
  content-visibility: auto;
  contain-intrinsic-size: 0 300px; /* estimated size to prevent CLS */
}
```

For full CSS architecture guide → `references/css-architecture.md`

---

## 4. JavaScript Patterns — Vanilla & Framework-Agnostic

### State Architecture Without a Framework

```js
// Minimal reactive store pattern (no dependencies)
function createStore(initialState) {
  let state = structuredClone(initialState);
  const listeners = new Set();

  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...patch };
      listeners.forEach(fn => fn(state));
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn); // unsubscribe
    }
  };
}

const clipStore = createStore({ jobs: [], status: 'idle' });
```

### DOM Update Strategy — The Reconciliation Decision

| Situation | Strategy |
|-----------|----------|
| Single value update (counter, status text) | Direct `textContent` / `dataset` mutation |
| Small list (< 50 items) | innerHTML template string (fast enough) |
| Large list (> 50 items) or frequent updates | Key-based reconciliation or Web Component |
| Real-time (polling/websocket), DOM-heavy | Lit or Svelte — they solve this correctly |

**Template pattern for small components**:
```js
function renderClipCard(job) {
  return `
    <article class="clip-card" data-id="${job.id}" data-status="${job.status}">
      <span class="clip-status clip-status--${job.status}">${job.status}</span>
      <h3 class="clip-title">${escapeHtml(job.title)}</h3>
      <div class="clip-actions">
        ${job.status === 'ready' ? `<a href="${job.clip_url}" class="btn btn--primary">Abrir clip</a>` : ''}
        ${job.status === 'failed' ? `<button class="btn btn--ghost" data-action="retry" data-id="${job.id}">Tentar novamente</button>` : ''}
      </div>
    </article>
  `;
}
```

**ALWAYS escape user-generated content** (`escapeHtml` is mandatory):
```js
function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
```

### Event Delegation — One Handler Rules All

```js
// ✅ One listener for the entire list (not one per card)
document.querySelector('.clips-container').addEventListener('click', e => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;

  const { action, id } = btn.dataset;
  if (action === 'retry') retryJob(id);
  if (action === 'copy') copyToClipboard(btn.dataset.url);
});
```

For complete JS patterns → `references/js-performance.md`

---

## 5. Dashboard & Real-Time UI Patterns

### Polling Architecture (the right way)

```js
// Adaptive polling — slows down when tab is hidden
class Poller {
  #interval;
  #fn;
  #ms;
  #visibilityFactor = 1;

  constructor(fn, ms = 3000) {
    this.#fn = fn;
    this.#ms = ms;
    document.addEventListener('visibilitychange', () => {
      this.#visibilityFactor = document.hidden ? 5 : 1;
    });
  }

  start() {
    const tick = async () => {
      await this.#fn();
      this.#interval = setTimeout(tick, this.#ms * this.#visibilityFactor);
    };
    tick();
    return this;
  }

  stop() { clearTimeout(this.#interval); }
}
```

### Status Card Component Pattern

Each clip job has `queued | creating | polling | ready | failed`.
Map states to CSS data attributes — never to classes (data attrs are cheaper to parse):

```css
[data-status="queued"]  { --card-accent: var(--color-status-pending); }
[data-status="ready"]   { --card-accent: var(--color-status-success); }
[data-status="failed"]  { --card-accent: var(--color-status-error); }
[data-status="creating"],
[data-status="polling"] { --card-accent: var(--color-status-pending); }

.clip-card::before {
  background: var(--card-accent);
  /* accent bar driven purely by CSS — zero JS for visual state */
}
```

### Skeleton Loading — Prevent CLS

```css
.skeleton {
  background: linear-gradient(
    90deg,
    var(--color-bg-skeleton) 25%,
    var(--color-bg-skeleton-shine) 50%,
    var(--color-bg-skeleton) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; opacity: 0.5; }
}
```

**Always reserve exact height** for skeleton containers to match final content height.

### Optimistic UI Pattern

Show the result before the server confirms. Rollback on error.

```js
async function retryJob(id) {
  // 1. Optimistic update
  updateJobStatus(id, 'creating');

  try {
    await api.retryClipJob(id);
    // 2. Server confirmed — polling will pick up real status
  } catch(err) {
    // 3. Rollback
    updateJobStatus(id, 'failed');
    showError(`Retry falhou: ${err.message}`);
  }
}
```

For complete dashboard patterns → `references/dashboard-patterns.md`

---

## 6. Accessibility as Performance

Accessibility is not optional — it's a performance multiplier. Screen readers, keyboard users, and cognitive load all affect conversion and retention.

**The non-negotiables**:
- Every interactive element reachable by `Tab` key
- `aria-live="polite"` on any region that updates dynamically (status, error messages)
- Color contrast ≥ 4.5:1 for body text, ≥ 3:1 for UI elements (WCAG 2.2 AA)
- `prefers-reduced-motion` respected on ALL animations
- Error messages: visible text + icon + color (never color alone)
- Focus visible: `outline` styles explicitly defined (browsers vary)

```css
/* Never suppress focus without an alternative */
:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}
```

---

## 7. Asset Performance Checklist

- [ ] Images: use WebP (with `<picture>` + JPG fallback), `loading="lazy"` for below-fold
- [ ] Fonts: self-hosted > Google Fonts. Use `font-display: swap`. Subset fonts.
- [ ] Icons: inline SVG > icon font > img sprite. Never icon fonts for single use.
- [ ] JS: one entry bundle, no `node_modules` for UI primitives
- [ ] CSS: critical inline in `<head>`, rest deferred
- [ ] No unused CSS (manually audit or use PurgeCSS in build)
- [ ] HTTP caching: static assets with content hash in filename (`main.a3f9c2.js`)

---

## 8. Code Review Checklist — Before Shipping

**Performance**:
- [ ] No layout-triggering reads inside loops
- [ ] Animations use only `transform`/`opacity`
- [ ] Event listeners use delegation where appropriate
- [ ] No memory leaks (event listeners removed on component teardown)
- [ ] `content-visibility` on large lists or offscreen sections

**Correctness**:
- [ ] User content always escaped
- [ ] Error states have visible, human-readable messages
- [ ] IDs (action_id, job_id) never mixed up in UI
- [ ] Retry limited (no infinite retry loops on permanent errors)

**UX**:
- [ ] Loading state visible (skeleton or spinner) within 100ms of action
- [ ] Success and failure feedback always present
- [ ] Destructive actions require confirmation
- [ ] Empty states are designed, not blank

---

## 9. Reference Files in This Skill

| File | When to Read |
|------|-------------|
| `references/stack-decision.md` | When choosing between vanilla/Svelte/Solid/Lit/Astro |
| `references/css-architecture.md` | When setting up CSS architecture or design system |
| `references/js-performance.md` | When optimizing JS, state management, DOM patterns |
| `references/dashboard-patterns.md` | When building polling UIs, real-time cards, status flows |
