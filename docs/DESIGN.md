# Wathiq design system

Premium, calm, bank-grade. Neutral branding — no bank names or logos. The product name mark is the
word **Wathiq** plus a small shield/check glyph.

## Principles
1. **Calm surface, loud signal.** Chrome is quiet greys; colour is reserved for confidence, risk and
   SLA state. If everything is coloured, nothing is.
2. **Evidence next to claim.** Any extracted value is shown with its confidence and a way to reach
   the source region in the document.
3. **Honest labels.** Simulated integrations are badged `Simulated`, demo ones `Demo`.
4. **Density with air.** Banking operators scan tables all day: compact rows, generous section gaps.

## Tokens (CSS variables, defined in `src/styles/theme.css` via Tailwind v4 `@theme`)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-bg` | `#F7F8FA` | `#0A0E14` | page background |
| `--color-surface` | `#FFFFFF` | `#111823` | cards, panels |
| `--color-surface-2` | `#F1F3F7` | `#18212E` | table headers, insets |
| `--color-border` | `#E3E7EE` | `#232E3D` | hairlines |
| `--color-ink` | `#0B1220` | `#E8EEF6` | primary text |
| `--color-ink-2` | `#5A6675` | `#93A1B2` | secondary text |
| `--color-primary` | `#0E5E5A` | `#2FA8A0` | brand, primary buttons, active nav |
| `--color-primary-soft` | `#E6F2F1` | `#0E2B2A` | primary tinted backgrounds |
| `--color-accent` | `#B58B2A` | `#D9B25C` | brand highlight only, used sparingly |
| `--color-success` | `#0F7A52` | `#3CC08A` | high confidence, approved, on track |
| `--color-warning` | `#A65F17` | `#E0A458` | medium confidence, at risk |
| `--color-danger` | `#B3261E` | `#F2837B` | low confidence, breached, rejected |
| `--color-info` | `#1D4ED8` | `#7BA2F5` | neutral information |

Radii: `--radius-sm 6px`, `--radius 10px`, `--radius-lg 14px`. Shadows: one soft elevation for
cards (`0 1px 2px rgb(11 18 32 / .04), 0 4px 16px rgb(11 18 32 / .06)`), one for popovers.
Spacing: 4px base scale (Tailwind default). Container max width 1440px.

## Typography
- Latin: **Inter Variable** (`@fontsource-variable/inter`), self-hosted so the demo works offline.
- Arabic: **IBM Plex Sans Arabic** (`@fontsource/ibm-plex-sans-arabic`), applied under `[dir="rtl"]`.
- Numbers in tables use `font-variant-numeric: tabular-nums`.
- Scale: display 30/36 semibold · h1 24/32 semibold · h2 18/28 semibold · body 14/22 · small 13/20 ·
  caption 12/16 uppercase tracking-wide for table headers and labels.

## Core components (hand-written in the shadcn/ui style: Radix primitives + `cva` + `cn`)
Button, IconButton, Input, Textarea, Select, Checkbox, Switch, Badge, StatusPill, ConfidenceBadge,
Card, StatCard, Table (sortable, sticky header), Tabs, Dialog, Sheet, DropdownMenu, Tooltip, Toast,
Skeleton, EmptyState, ErrorState, Progress, Stepper, Timeline, Avatar, Pagination, SearchInput,
DateRange, CodeBlock, MermaidDiagram, CommandPalette (⌘K).

## Semantic patterns
- **ConfidenceBadge**: ≥0.90 success "High", 0.70–0.89 warning "Medium", <0.70 danger "Low".
  Always shows the number (`92%`) — never colour alone (WCAG: colour is never the only signal).
- **StatusPill** per `CaseStatus`, with a matching dot glyph.
- **SLA timer**: on track (grey), at risk <25% time left (warning, pulsing dot), breached (danger).
- **Simulated badge**: outline pill with a small flask icon, tooltip "Simulated service — no real
  external system is contacted."

## Accessibility (WCAG AA)
Visible focus ring (`2px` primary, `2px` offset) on every interactive element; all colour pairs meet
4.5:1 for text; every icon-only button has `aria-label`; tables use real `<th scope>`; dialogs trap
focus and restore it; live regions announce toasts and pipeline progress; full keyboard path through
the review workspace.

## States
Every data surface implements four states: **skeleton** (shimmer matching final layout), **empty**
(icon + one sentence + primary action), **error** (what failed + Retry), **loaded**.

## Layout
Fixed left sidebar (240px, collapsible to 64px icons) · top bar with case search (⌘K), mode badge
(`DEMO`/`AZURE`), language toggle (EN/العربية), theme toggle, user menu · content max 1440px with
24px gutters · responsive: sidebar becomes a sheet under 1024px, tables become cards under 768px.
