# Security

BIDSHub is a **single-user, local-first** desktop application. It is **not** designed as a hardened multi-tenant internet service.

## Reporting a vulnerability

If you find a security issue in **this repository’s code** (not in third-party platforms such as Pennsieve or OpenNeuro), please report it privately to the maintainers (e.g. via a private security advisory on the project’s host, if available, or contact the repository owner). Do not post exploit details in public issues until a fix is agreed.

## Credentials and data

- Never commit **`.env`**, API keys, or database files that contain sensitive workflow data to a public repository.
- Rotate keys in the **provider’s console** (Pennsieve, etc.) if they are ever exposed.
- Treat local `data/*.db` like any file with metadata about your research workflow: back up and share under your institution’s rules.

## Network exposure

Running the app with Streamlit bound to **all interfaces** (e.g. `0.0.0.0`) on a machine reachable from untrusted networks increases risk. Prefer **localhost** for normal use. If you use **Docker** with a published port, restrict access with host firewalls or a reverse proxy with authentication and TLS.

## Third parties

Use of cloud platforms (Pennsieve, OpenNeuro, XNAT, DANDI, …) is subject to their terms, security practices, and incident response. BIDSHub stores **your** API credentials **locally** as configured in the app or `.env`.
