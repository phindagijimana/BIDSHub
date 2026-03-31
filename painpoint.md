# BIDSHub: problems we solve

BIDSHub is aimed at **neuroimaging researchers** who work with **BIDS** data spread across **many systems**. In practice it targets these problems.

## Fragmentation across platforms

Data live on OpenNeuro, Pennsieve, DANDI, XNAT, local disks, HPC, and other environments, each with its own UI and workflow. BIDSHub gives **one desktop app** to connect several sources and **see subjects in one place** (many datasets at once).

## Wasted time and storage

Researchers often need only **some subjects** or **some scans**. The app supports **metadata filtering** (age, sex, diagnosis, keywords, modalities) and **queued, batched downloads** so you can pull **only what you need** instead of whole portals or oversized archives.

## Inconsistent structure and metadata

Different sites organize data differently. By **standardizing on BIDS** (and validating on add), BIDSHub pushes a **shared layout and comparable fields** so browsing and filtering work **the same way** across sources.

## Browse before you commit

It supports **browsing structure and metadata before heavy downloads**, and a **built-in NIfTI viewer** so you can sanity-check images without assembling a separate tool chain for every step.

## QC and cohort building across studies

It helps **track quality control** across datasets and sessions and **build cohorts** that mix institutions and platforms—without standing up your own multi-user data platform.

## Moving data between environments

**Data transfer** (for example local ↔ Pennsieve, HPC, XNAT, remote server) addresses the gap between “data on a cluster or archive” and “data on my machine.”

## What BIDSHub is not trying to solve

- **Analysis pipelines** (use tools such as fMRIPrep, FreeSurfer, etc.).
- **Multi-user collaboration** (single user per installation).
- **Hosted cloud infrastructure** (runs locally).

In short, BIDSHub is a **single-user, local** hub for **discovery, filtering, download, QC, viewing, and transfer** around BIDS-formatted neuroimaging data.

## See also

- [UX.md](UX.md) — how we want the product to feel polished and calm (less noise, clearer flows).
