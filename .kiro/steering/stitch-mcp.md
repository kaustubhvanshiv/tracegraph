---
inclusion: always
---

# Google Stitch MCP — TraceGraph Frontend Workflow

## What is Stitch MCP

Google Stitch is an AI UI-generation service at `stitch.withgoogle.com`. It generates HTML/CSS screens from natural-language prompts. The Stitch MCP server exposes those screens and design tools directly to this Kiro agent so it can pull design HTML/screenshots into the TraceGraph frontend build without leaving the IDE.

The MCP server is configured at:
```
tracegraph/.kiro/settings/mcp.json
```
It uses the `stitch-mcp-stdio` package (stable stdio transport — no proxy crash on Windows).  
Authentication is via `STITCH_API_KEY` in `tracegraph/.env` (already set, never commit this file).

---

## Available Stitch MCP Tools

Confirmed live from `stitch.googleapis.com/mcp` on 2026-10-02. These are the exact tools returned by the server:

| Tool | What it does | Notes |
|---|---|---|
| `create_project` | Create a new Stitch project | Container for all screens |
| `get_project` | Get metadata for a specific project by name | |
| `delete_project` | Delete a project — **irreversible** | Server asks for confirmation before proceeding |
| `list_projects` | List all projects owned by the account | |
| `list_screens` | List all screens within a project | |
| `get_screen` | Get details of a specific screen | Use this to poll after timeouts |
| `generate_screen_from_text` | Generate a new screen from a text prompt | **Takes minutes — do NOT retry on timeout.** Poll with `get_screen` every 30s up to 10 times |
| `edit_screens` | Edit existing screen(s) with a new prompt | Takes minutes — same timeout rule |
| `generate_variants` | Generate design variants of existing screens | Poll with `get_screen` on timeout |
| `upload_design_md` | Upload a DESIGN.md file to a project | **Must immediately call `create_design_system_from_design_md` after** |
| `create_design_system` | Create design system (colors, typography, shape, dark/light mode) | **Must immediately call `update_design_system` after** |
| `create_design_system_from_design_md` | Create design system from uploaded DESIGN.md | Call `upload_design_md` first |
| `update_design_system` | Update existing design system tokens | |
| `list_design_systems` | List design systems for a project | |
| `apply_design_system` | Apply design system tokens to one or more screens | |

### Agent rules from the server (must follow)
- After `generate_screen_from_text` / `generate_variants` times out — **do not retry**. Call `get_screen` every 30 seconds, up to 10 attempts.
- If a call fails due to a connection error, the generation may still succeed. Check with `get_screen` before assuming failure.
- Check `output_components` in the generate response. If it contains suggestions, present them to the user. If the user accepts one, re-call `generate_screen_from_text` with that suggestion as the `prompt`.

---

## Where to Find Frontend Tasks

Tasks for the TraceGraph frontend are located in:

```
tracegraph/Documents/TraceGraph_Implementation_Plan.md   ← ordered build plan (start here)
tracegraph/Documents/TraceGraph_Design_Document.md       ← component hierarchy, wireframes, API contracts
tracegraph/Documents/TraceGraph_Requirements_Document.md ← functional requirements per screen
```

The frontend section starts at **"React Investigation Workspace"** in the Implementation Plan.  
The component hierarchy (Part 3 of the Design Document) is the authoritative reference for what to build.

### Component Map (already scaffolded)

```
frontend/src/
├── pages/
│   ├── InvestigationsPage.tsx       ← investigation list / create new
│   └── WorkspacePage.tsx            ← main investigation workspace
├── components/
│   ├── Workspace/
│   │   ├── GraphPanel.tsx           ← Cytoscape.js graph
│   │   ├── TimelinePanel.tsx        ← chronological event list
│   │   ├── EvidencePanel.tsx        ← event detail / raw data
│   │   ├── AISummaryPanel.tsx       ← LLM-generated narrative
│   │   └── AnalystDecisionPanel.tsx ← outcome / notes
│   ├── InvestigationList/           ← list + creation UI
│   └── common/                      ← shared atoms
├── services/                        ← axios API calls
├── hooks/                           ← React custom hooks
└── types/                           ← TypeScript interfaces
```

Tech stack: **React 18 + TypeScript + Vite + Tailwind CSS + Cytoscape.js + React Router v6 + Axios**

---

## How to Use Stitch MCP to Build the Frontend

### Step 1 — Create a Stitch project for TraceGraph

```
create_project  →  name: "tracegraph-ui"
```

### Step 2 — Create a design system

Call `create_design_system` with dark theme tokens (dark background, monospace for technical values, high contrast), then immediately call `update_design_system` to apply it.

### Step 3 — Generate screens

Use `generate_screen_from_text` to produce reference HTML for each panel.  
Ground every prompt in the Design Document wireframes (Part 3).  
Do not retry on timeout — poll with `get_screen`.

### Step 4 — Apply the design system

Call `apply_design_system` across all generated screens for visual consistency.

### Step 5 — Translate to React/TypeScript

Pull screen HTML via `get_screen`. Convert it into the corresponding `.tsx` component.  
Map Stitch CSS classes to Tailwind equivalents. Wire up props and API callbacks.

---

## Stitch Prompt Seeds for Each Component

Use these as the starting point for `generate_screen_from_text`:

| Component file | Prompt seed |
|---|---|
| `WorkspacePage.tsx` | "Security investigation workspace, dark theme. Four-panel grid: top-left Cytoscape entity graph with colored node types, top-right chronological event timeline, bottom-left evidence detail card, bottom-right AI summary panel. Header with investigation title and status badge. Tailwind CSS. Monospace font for technical values." |
| `GraphPanel.tsx` | "Interactive entity relationship graph. Dark background. Nodes colored by type: User=blue, Host=green, Process=amber, Server=red, File=slate. Labeled directed edges. Selected node highlighted with ring. Zoom and pan controls. Sidebar shows selected entity details." |
| `TimelinePanel.tsx` | "Chronological security event list. Monospace timestamps. Color-coded event type badges (Auth / Network / Process / File). Scrollable. Filterable by entity and event type. Click a row to open event in evidence panel. Dark card." |
| `EvidencePanel.tsx` | "Security event detail card. Shows: event ID chip, source badge, UTC timestamp, key-value normalized fields table, collapsible raw JSON section, 'Supports relationship' chip showing graph edge. Dark card with monospace values." |
| `AISummaryPanel.tsx` | "'AI Generated' badge header. Structured sections: Overview / Chronological Sequence / Key Entities / Supporting Evidence IDs / Uncertainty. Evidence IDs as clickable chips. 'Review Evidence' button. Visually distinct from source data (different background)." |
| `AnalystDecisionPanel.tsx` | "Analyst decision card. Status radio buttons (Open / Under Review / Closed). Outcome dropdown (Continue Investigation / Escalate / Close as Investigated). Timestamped notes textarea. Save button. Kept visually separate from AI output panel." |
| `InvestigationsPage.tsx` | "Security investigations list page. Table with columns: title, status badge (color-coded), created date, event count, Open button. Empty state illustration. Top-right 'New Investigation' button opens a modal form with title and description fields." |

---

## Key Design Rules (from Design Document — must follow)

- The graph and timeline **must share the same evidence IDs** so selecting a node or timeline row cross-links to the same source event in the Evidence Panel.
- The **Evidence Panel** is the auditability view — always show: `event_id`, `source`, `timestamp`, normalized fields, and which graph relationship the event supports.
- The **AI Summary Panel** must visually distinguish AI-generated text from source evidence citations (different background or border).
- The **Analyst Decision Panel** must be kept separate from AI output — the analyst makes the final call, never the LLM.
- Selecting a graph **node** → show entity type, name, and supporting events.
- Selecting a graph **edge** → show relationship type, timestamp, event IDs, source, and correlation signals.
- Timeline order is **always by event timestamp** — never reorder by graph importance or correlation score.

---

## Backend API Endpoints (FastAPI, port 8000)

```
POST   /api/investigations
GET    /api/investigations
GET    /api/investigations/{id}
PATCH  /api/investigations/{id}

POST   /api/investigations/{id}/events
GET    /api/investigations/{id}/events
GET    /api/events/{event_id}

GET    /api/investigations/{id}/graph
GET    /api/investigations/{id}/graph/pivot

GET    /api/investigations/{id}/timeline

POST   /api/investigations/{id}/summary
GET    /api/investigations/{id}/summary

POST   /api/investigations/{id}/notes
PATCH  /api/investigations/{id}/outcome
PATCH  /api/investigations/{id}/status
```

Frontend Vite dev server: **port 5173**. CORS origin `http://localhost:5173` is already configured in the backend `.env`.
