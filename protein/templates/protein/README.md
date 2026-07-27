# ProteinMaster Django templates

`workspace.html` is the complete interactive page exposed at `/protein/`.

Reusable components:

- `components/header.html` — page identity and live workflow status.
- `components/tissue_panel.html` — tissue presets and custom tissue input.
- `components/query_panel.html` — functional annotation and protein-type controls.
- `components/results_panel.html` — ranked protein output and JSON export.

The browser interaction lives in `static/protein/workspace.js`; visual tokens
and responsive layout live in `static/protein/workspace.css`.
