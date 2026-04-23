# BIDSHub

**Multi-platform neuroimaging dataset management and exploration** — browse, filter, and download BIDS datasets from several platforms in one place.

**Datasets must be [BIDS](https://bids.neuroimaging.io/).** BIDSHub validates on add. Platform-specific caveats, conversion help, and full workflows: **[USER_GUIDE.md](USER_GUIDE.md)**.

## Quick start (CLI)

```bash
git clone <repo-url> && cd BIDSHUB
```

| | **Native** (Python on the host) | **Docker** (Compose v2; bash / WSL) |
|---|--------------------------------|--------------------------------------|
| **Install & run** | `./hub install && ./hub start` | `./hub-docker install && ./hub-docker start` |
| **Help** | `./hub help` | `./hub-docker help` |
| **Typical ops** | `./hub status` · `./hub logs` · `./hub stop` · `./hub restart` | `./hub-docker checks` · `./hub-docker logs` · `./hub-docker stop` · `./hub-docker restart` |

First run can create **`.env`** from **`.env.example`**. App URL: **`http://localhost:8501`** (or next free port in **8501–8551**; override with **`BIDSHUB_DEFAULT_PORT`** or **`BIDSHUB_HOST_PORT`** in `.env` for Docker).

**Windows (native):** `bin\explorer.bat`.

**Pre-built image:** set `BIDSHUB_DOCKER_FILE=docker-compose.image.yml` and `BIDSHUB_IMAGE=…`, then `./hub-docker pull && ./hub-docker start` — see [USER_GUIDE.md](USER_GUIDE.md#overview-bids-and-installation) and [RELEASING.md](RELEASING.md).

**Security:** keep secrets in **`.env`** (never commit). Do not expose Streamlit to the public internet without TLS and auth — [SECURITY.md](SECURITY.md).

## Documentation

| Doc | Use for |
|-----|--------|
| **[USER_GUIDE.md](USER_GUIDE.md)** | BIDS, platforms, install details, first run, features, workflows |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | Common errors and fixes |
| **[SECURITY.md](SECURITY.md)** | Credentials and network |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Development setup (optional) |

## License

MIT — see [LICENSE](LICENSE).

## Support

**Issues:** [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues)

---

**Version 3.1.1** · Status: production
