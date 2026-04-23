# BIDSHub

**Multi-platform neuroimaging dataset management and exploration** — browse, filter, and download BIDS datasets from several platforms in one place.

**Datasets must be [BIDS](https://bids.neuroimaging.io/).** BIDSHub validates on add.

## Documentation (three files)

| | |
|---|---|
| **[USER_GUIDE.md](USER_GUIDE.md)** | BIDS, platforms, install (native + Docker), workflows, security, and maintainer notes |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | Install, pip, venv, Docker, platform issues, and fixes |
| **README.md** (this file) | Short intro and CLI only |

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

**Pre-built image:** `BIDSHUB_DOCKER_FILE=docker-compose.image.yml`, `BIDSHUB_IMAGE=…`, then `./hub-docker pull && ./hub-docker start` — see [USER_GUIDE.md](USER_GUIDE.md#native-and-docker-cli).

**Secrets:** keep API keys in **`.env`** only (never commit).

## License

MIT — see [LICENSE](LICENSE).

## Support

**Issues:** [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues)

**Version 3.1.1**
