# CSS Architecture — Deep Reference

> Philosophy: CSS is a design system language. Write it like one.
> Every line of CSS is a decision. Every decision must be intentional.

---

## Layer Architecture (Cascade Layers — Modern Standard)

```css
/* Define order once at the top of your main CSS file */
@layer reset, tokens, base, layout, components, utilities, overrides;

/* Each layer has lower priority than layers defined after it */
/* This means .overrides always wins — no !important needed */
```

### Layer Responsibilities

| Layer | Purpose | Example |
|-------|---------|---------|
| `reset` | Kill browser defaults | `* { box-sizing: border-box; margin: 0; }` |
| `tokens` | CSS custom properties | `--color-*, --space-*, --radius-*` |
| `base` | Typography, element defaults | `h1-h6`, `a`, `button` base styles |
| `layout` | Page structure | `.sidebar`, `.main`, `.grid` |
| `components` | UI components | `.clip-card`, `.btn`, `.badge` |
| `utilities` | One-off helpers | `.sr-only`, `.truncate`, `.flex-center` |
| `overrides` | Context-specific exceptions | Vendor overrides, emergency fixes |

---

## Design Token System — Complete Implementation

### Token Naming Convention (3-tier hierarchy)

```css
/* Pattern: --[category]-[concept]-[variant]-[state] */

/* Primitive tokens (VALUES — never reference directly in components) */
:root {
  /* Colors */
  --primitive-blue-100: #dbeafe;
  --primitive-blue-500: #3b82f6;
  --primitive-blue-900: #1e3a5f;
  --primitive-green-500: #22c55e;
  --primitive-red-500: #ef4444;
  --primitive-amber-500: #f59e0b;
  --primitive-gray-50:  #f8fafc;
  --primitive-gray-100: #f1f5f9;
  --primitive-gray-800: #1e293b;
  --primitive-gray-900: #0f172a;

  /* Spacing scale (4px base) */
  --primitive-space-1: 4px;
  --primitive-space-2: 8px;
  --primitive-space-3: 12px;
  --primitive-space-4: 16px;
  --primitive-space-6: 24px;
  --primitive-space-8: 32px;
  --primitive-space-12: 48px;
  --primitive-space-16: 64px;

  /* Type scale */
  --primitive-text-xs:   0.75rem;
  --primitive-text-sm:   0.875rem;
  --primitive-text-base: 1rem;
  --primitive-text-lg:   1.125rem;
  --primitive-text-xl:   1.25rem;
  --primitive-text-2xl:  1.5rem;

  /* Radii */
  --primitive-radius-sm: 4px;
  --primitive-radius-md: 8px;
  --primitive-radius-lg: 12px;
  --primitive-radius-full: 9999px;

  /* Motion */
  --primitive-duration-fast:   120ms;
  --primitive-duration-normal: 250ms;
  --primitive-duration-slow:   400ms;
  --primitive-ease-out:  cubic-bezier(0.25, 0, 0, 1);
  --primitive-ease-in:   cubic-bezier(0.4, 0, 1, 1);
  --primitive-ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

```css
/* Semantic tokens (PURPOSE — what components use) */
:root {
  /* Surface colors */
  --color-bg-app:          var(--primitive-gray-900);
  --color-bg-card:         var(--primitive-gray-800);
  --color-bg-input:        #1a2030;
  --color-bg-skeleton:     #252d3d;
  --color-bg-skeleton-shine: #2e3a4e;

  /* Text colors */
  --color-text-primary:    #e2e8f0;
  --color-text-secondary:  #94a3b8;
  --color-text-muted:      #64748b;
  --color-text-inverse:    var(--primitive-gray-900);

  /* Status colors (semantic — these change meaning in light/dark) */
  --color-status-success:  var(--primitive-green-500);
  --color-status-error:    var(--primitive-red-500);
  --color-status-warning:  var(--primitive-amber-500);
  --color-status-pending:  var(--primitive-blue-500);
  --color-status-info:     var(--primitive-blue-500);

  /* Border */
  --color-border-subtle:   rgba(255, 255, 255, 0.08);
  --color-border-default:  rgba(255, 255, 255, 0.12);
  --color-border-strong:   rgba(255, 255, 255, 0.2);
  --color-focus-ring:      var(--primitive-blue-500);

  /* Spacing aliases */
  --space-card-padding:    var(--primitive-space-4);
  --space-section-gap:     var(--primitive-space-6);
  --space-list-gap:        var(--primitive-space-3);

  /* Component tokens */
  --btn-height-sm:         32px;
  --btn-height-md:         40px;
  --btn-radius:            var(--primitive-radius-md);

  /* Motion tokens */
  --transition-ui:         var(--primitive-duration-fast) var(--primitive-ease-out);
  --transition-expand:     var(--primitive-duration-normal) var(--primitive-ease-out);
  --transition-enter:      var(--primitive-duration-normal) var(--primitive-ease-spring);
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --transition-ui: 0ms linear;
    --transition-expand: 0ms linear;
    --transition-enter: 0ms linear;
  }
}
```

---

## Component Architecture Pattern

### The Card Component (full example)

```css
@layer components {
  .clip-card {
    /* Layout */
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: var(--primitive-space-2);
    padding: var(--space-card-padding);

    /* Visual */
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--primitive-radius-lg);
    border-top: 3px solid var(--card-accent, var(--color-border-subtle));

    /* Performance: isolate this component's layout */
    contain: content;

    /* Transition only on cheap properties */
    transition: border-color var(--transition-ui),
                box-shadow var(--transition-ui);
  }

  /* Status drives accent via data attribute — NO JS class toggling */
  [data-status="queued"]  { --card-accent: var(--color-status-pending); }
  [data-status="creating"] { --card-accent: var(--color-status-warning); }
  [data-status="polling"] { --card-accent: var(--color-status-warning); }
  [data-status="ready"]   { --card-accent: var(--color-status-success); }
  [data-status="failed"]  { --card-accent: var(--color-status-error); }

  .clip-card:hover {
    border-color: var(--color-border-strong);
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  }
}
```

---

## Layout Systems

### Grid-first, Flexbox-second

- **CSS Grid**: for 2D layout (rows AND columns), page structure, card grids
- **Flexbox**: for 1D layout (a row of items, or a column), component internals

```css
/* Dashboard layout */
.dashboard {
  display: grid;
  grid-template-columns: 240px 1fr;
  grid-template-rows: 60px 1fr;
  grid-template-areas:
    "sidebar header"
    "sidebar main";
  height: 100dvh; /* dvh = dynamic viewport height, mobile-safe */
}

/* Card grid — auto-fill means no JS for responsive */
.clips-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-list-gap);
}
```

### Container Queries (2024+ standard — use them)

```css
/* Instead of viewport media queries, respond to container size */
.card-container {
  container-type: inline-size;
  container-name: card;
}

@container card (min-width: 480px) {
  .clip-card {
    grid-template-columns: 1fr auto;
  }
}
```

---

## CSS Performance Rules

1. **Prefer class selectors** over element+class combinators for perf. `.btn` > `button.btn`
2. **Avoid deep nesting** (> 3 levels). Flat CSS is faster to parse.
3. **`contain: content`** on repeated components. Tells browser to skip layout outside the container.
4. **`will-change: transform`** only right before an animation starts; remove it after. Don't add globally.
5. **`content-visibility: auto`** for long lists with offscreen items. **Huge** perf gain on large lists.
6. Never use `*` selector for anything other than reset (it's slow on complex DOMs).
7. Keep `@keyframes` simple — only animate `transform` and `opacity`.

```css
/* Off-screen list items — browser skips their rendering entirely */
.clips-list .clip-card {
  content-visibility: auto;
  contain-intrinsic-block-size: 140px; /* estimated, prevents CLS */
}
```

---

## Typography System

```css
@layer base {
  :root {
    --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', 'Cascadia Code', ui-monospace, monospace;
    font-size: 16px; /* base — never set on body, only root */
  }

  body {
    font-family: var(--font-sans);
    font-size: var(--primitive-text-base);
    line-height: 1.5;
    color: var(--color-text-primary);
    background: var(--color-bg-app);
    -webkit-font-smoothing: antialiased;
  }

  /* Type scale */
  .text-xs   { font-size: var(--primitive-text-xs); }
  .text-sm   { font-size: var(--primitive-text-sm); }
  .text-base { font-size: var(--primitive-text-base); }
  .text-lg   { font-size: var(--primitive-text-lg); }

  /* Semantic */
  .text-muted    { color: var(--color-text-muted); }
  .text-secondary { color: var(--color-text-secondary); }

  /* Mono for IDs, technical values */
  .text-mono { font-family: var(--font-mono); font-size: 0.85em; }
}
```

---

## Button System (complete, zero-dependency)

```css
@layer components {
  .btn {
    /* Reset */
    all: unset;
    /* Layout */
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--primitive-space-2);
    /* Sizing */
    height: var(--btn-height-md);
    padding: 0 var(--primitive-space-4);
    /* Type */
    font-family: var(--font-sans);
    font-size: var(--primitive-text-sm);
    font-weight: 500;
    white-space: nowrap;
    /* Visual */
    border-radius: var(--btn-radius);
    cursor: pointer;
    transition: background var(--transition-ui),
                opacity var(--transition-ui),
                transform var(--transition-ui);
    /* Accessibility */
    user-select: none;
  }

  .btn:focus-visible {
    outline: 2px solid var(--color-focus-ring);
    outline-offset: 2px;
  }

  .btn:active {
    transform: scale(0.97);
  }

  .btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    pointer-events: none;
  }

  /* Variants */
  .btn--primary {
    background: var(--primitive-blue-500);
    color: white;
  }
  .btn--primary:hover { background: var(--primitive-blue-100); color: var(--primitive-gray-900); }

  .btn--danger {
    background: var(--color-status-error);
    color: white;
  }

  .btn--ghost {
    background: transparent;
    color: var(--color-text-secondary);
    border: 1px solid var(--color-border-default);
  }
  .btn--ghost:hover {
    background: rgba(255,255,255,0.05);
    color: var(--color-text-primary);
  }

  /* Sizes */
  .btn--sm { height: var(--btn-height-sm); padding: 0 var(--primitive-space-3); font-size: var(--primitive-text-xs); }
}
```
