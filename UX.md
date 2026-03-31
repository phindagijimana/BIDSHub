# BIDSHub: UX direction — flourish without noise

This document captures **product and UX principles** for making the app feel finished and calm: smooth, trustworthy, and not chatty. It complements [painpoint.md](painpoint.md) (why the product exists).

## 1. Turn down message volume

The main UI (`app.py`) uses many `st.info` / `st.warning` / `st.error` / `st.success` calls. Streamlit reruns amplify that into **banner fatigue**.

- Prefer **one primary message per region** (e.g. one strip under the page title, or one inline hint next to the control).
- Use **`st.toast()`** for short-lived confirmations (“Loaded”, “Queued”) instead of persistent success banners.
- Put **long explanations** (OpenNeuro download steps, BIDS rules) in **expanders** (“Help”, “Why am I seeing this?”) instead of repeating large `st.info` blocks on every run.

## 2. Quiet empty and edge states

- **Empty subject lists** and similar “not yet synced” states are **expected**, not errors. Prefer **neutral copy** or `st.caption` over warning styling.
- One short line plus **a single clear action** (“Open Manage Datasets”, “Sync”) beats several stacked info blocks.

## 3. Smooth async work without drama

- For downloads, DANDI streaming, SSH operations: use **one** progress pattern (spinner or progress bar); avoid spinner + info + success for the same step.
- Where the network is flaky: **retry** modestly, then **one** clear error with a **Retry** action—no duplicate error banners.

## 4. Close product gaps without surprising the user

- Flows that can be started from the UI but are not implemented (e.g. download queue vs platform) **erode trust**. Prefer **disable + tooltip** or hiding the action until supported, over a surprise warning at click time.
- **Beta platforms** (e.g. XNAT): a **single dismissible** note (e.g. session state), not repeated warnings on every visit.

## 5. Consistency = fluency

- Reuse the same verbs: **Sync**, **Load**, **Queue**, **Transfer**.
- Centralize **connection and credential status** where possible (e.g. Manage Datasets or a compact header), instead of repeating connection hints on every page.

## 6. Performance = perceived polish

- Lean on **metadata caching** and avoid unnecessary heavy reruns so the UI does not flicker or replay messages.
- Large NIfTI in the browser: keep **one** calm inline path (external viewer suggestion) aligned with size limits—avoid stacking multiple alerts.

## 7. Onboarding without tutorial noise

- Optional **first-run** guidance in **one** place (checklist or “Getting started”), not banners on every screen.
- Strong **defaults** and documented sample paths reduce the need for explanatory copy everywhere.

## Summary

**Calm is a feature.** Fewer persistent banners, neutral tone for expected empty states, toasts for transient feedback, and **no surprise warnings** for incomplete flows—these are the main levers to make BIDSHub feel mature without adding noise.

## Implementation (in repo)

- [`src/ui_calm.py`](src/ui_calm.py) — helpers: `toast_ok`, `toast_note`, `expected_empty`, `quiet_queue_empty`, `DOWNLOAD_QUEUE_PLATFORMS`, `render_xnat_beta_notice`.
- [`app.py`](app.py) — download queue filters unsupported platforms before execution (one toast instead of per-batch warnings); queue/transfer/viewer/QC copy toned down; XNAT beta dismissible strip when adding a dataset; OpenNeuro viewer help moved to an expander; several `st.success`/`st.info` flows use toasts or captions.
