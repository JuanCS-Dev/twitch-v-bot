# Stack Decision Reference

> Read this when choosing a frontend stack. Never choose a framework for its popularity.
> Choose it based on measurable trade-offs for your specific requirements.

---

## Performance Benchmarks (js-framework-benchmark, 2024-2025)

Lower = faster. Vanilla JS = 1.0 baseline.

| Framework | DOM Create | DOM Update | Bundle (gzip) | Runtime Cost |
|-----------|-----------|-----------|---------------|-------------|
| Vanilla JS | 1.00 | 1.00 | 0 KB | none |
| Lit 3 | 1.05 | 1.02 | ~6 KB | minimal |
| SolidJS | 1.08 | 1.04 | ~7 KB | minimal |
| Svelte 5 | 1.10 | 1.06 | ~8 KB | minimal |
| Vue 3 | 1.30 | 1.25 | ~34 KB | moderate |
| React 18 | 1.45 | 1.35 | ~45 KB | moderate |
| Angular 17 | 1.60 | 1.50 | ~70 KB | heavy |

**Key insight**: Svelte and Solid pay near-zero runtime cost because they compile away to optimized DOM operations. React/Vue carry a virtual DOM runtime you always pay for, even if your UI doesn't need it.

---

## Decision Matrix

### Vanilla JS + Web Components
**Best for**: Internal dashboards, tools, existing vanilla codebases, performance-critical widgets
**Bundle**: 0 KB framework overhead
**Pros**: No build required, runs anywhere, no deprecation risk, platform-native
**Cons**: Manual DOM reconciliation for complex state, more boilerplate
**When to use**: Single-file apps, dashboard modules, when team knows JS well

### Lit 3
**Best for**: Reusable Web Components, design systems, micro-frontends
**Bundle**: ~6 KB
**Pros**: Standards-based (Custom Elements), works in any framework or none, template literals
**Cons**: Shadow DOM can complicate global CSS; smaller community
**When to use**: Component libraries, when components need to work across frameworks

### SolidJS
**Best for**: Complex interactive UIs, real-time data, React-like DX at near-vanilla performance
**Bundle**: ~7 KB
**Pros**: Fastest reactive framework, no virtual DOM, fine-grained reactivity, signals-first
**Cons**: Different mental model from React (no re-renders), smaller ecosystem
**When to use**: Replacing React where performance matters, new complex SPAs

### Svelte 5 (Runes)
**Best for**: Dashboards, apps where DX matters as much as performance
**Bundle**: ~8 KB
**Pros**: Compiles away framework, minimal JS shipped, intuitive reactivity with runes (`$state`, `$derived`)
**Cons**: Requires build step, smaller ecosystem than React
**When to use**: New projects where the team wants framework DX without framework overhead

### Astro
**Best for**: Content sites, landing pages, docs, marketing — any page where most content is static
**Bundle**: 0 KB by default (JS added per "island" only)
**Pros**: Zero JS by default, island architecture for partial hydration, supports any framework inside
**Cons**: Not for SPAs, no client-side routing by default
**When to use**: Any site where most pages don't need JS

### React (with Next.js or Vite)
**Best for**: Large teams with existing React skills, when ecosystem breadth matters more than raw performance
**Bundle**: ~45 KB
**Pros**: Largest ecosystem, best tooling, hiring pool
**Cons**: Virtual DOM overhead, bundle size, hydration complexity
**When to use**: Only when team is already React, or external constraints require it

---

## For This Dashboard Project (Twitch Bot)

**Recommendation: Vanilla JS + progressive Web Component adoption**

Rationale:
1. Dashboard already exists in vanilla JS — migration cost > benefit
2. Internal tool — no SEO, no SSR needed
3. Main interaction pattern is polling → render small lists → handle button clicks
4. This is within vanilla JS's sweet spot
5. If polling + reactive state becomes complex: **introduce Lit** for components only, no full rewrite

**Migration path if needed**:
```
Vanilla JS (now) 
  → Vanilla JS + Lit components (if state complexity grows)
  → Svelte (if full rebuild warranted and team agrees)
```

---

## Anti-patterns to Refuse

- Never install React for a dashboard that polls an API and renders cards
- Never use Next.js for an internal tool with no SEO requirements
- Never import a UI library (MUI, Chakra, etc.) for 2-3 components — write them
- Never use TypeScript's strict mode as an excuse for slow delivery on simple UIs
- Never reach for a state management library before you've tried a simple store pattern
