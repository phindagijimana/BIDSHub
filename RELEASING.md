# Releasing BIDSHub

## Version bump

1. Set **`__version__`** in **`src/bidshub_version.py`** (single source; **`python3 scripts/print_bidshub_version.py`** prints it for Docker, **`./hub-docker`** exports **`BIDSHUB_VERSION`** / defaults **`BIDSHUB_IMAGE`**, and **CI** reads it for image labels).
2. Match the **`version`** in **`pyproject.toml`**.
3. Update **`ARG BIDSHUB_VERSION=…`** in the **`Dockerfile`** (fallback when the build-arg is not passed) and the **`${…:-3.1.1}`** fallbacks in **`docker-compose.yml`** and **`docker-compose.image.yml`** so plain `docker compose` without env still uses the right default tag, or at least a coherent tag after your release.
4. Add a section to **`CHANGELOG.md`**, then tag: **`git tag vX.Y.Z && git push origin vX.Y.Z`** (adjust remote).

## PyPI (optional, not set up by default)

Publishing to PyPI would require:

- A proper **build backend** in `pyproject.toml` (e.g. hatchling or setuptools with `packages`),
- Clear **entry point** or documented `streamlit run app.py` from an installable layout,
- Maintenance of **release automation** (e.g. trusted publishing).

Until that exists, treat **git + tags + optional Docker image** as the release channel. See `docs/RELEASE_POLICY.md`.

## Docker image (build and push)

The **`Dockerfile`** produces an OCI image with **Streamlit** on port **8501**, **SQLite** under **`/app/data`**, and process user **uid 1000** (see **README** for bind-mount permissions).

**Build from repo root (version from source):**

```bash
V="$(python3 scripts/print_bidshub_version.py)"
docker build -t "bidshub:${V}" --build-arg "BIDSHUB_VERSION=${V}" .
```

**Or use compose / `./hub-docker install`** (exports **`BIDSHUB_VERSION`** from the script and builds **`bidshub:<version>`**).

**Push to a registry (example):**

```bash
V="$(python3 scripts/print_bidshub_version.py)"
REG=ghcr.io/YOUR_ORG
docker build -t "${REG}/bidshub:${V}" -t "${REG}/bidshub:latest" --build-arg "BIDSHUB_VERSION=${V}" .
docker push "${REG}/bidshub:${V}"
docker push "${REG}/bidshub:latest"
```

**Deploy a pre-pulled image** (no `Dockerfile` on the target host, only `docker-compose.image.yml` + env):

```bash
export BIDSHUB_DOCKER_FILE=docker-compose.image.yml
V="$(python3 scripts/print_bidshub_version.py)"
export BIDSHUB_IMAGE="ghcr.io/YOUR_ORG/bidshub:${V}"
./hub-docker pull    # or ./hub-docker install
./hub-docker start
```

Document the **registry URL and tag** for your users. Use **private** registries if required by policy.
