# `.observability/` — runtime artifacts

Holds ephemeral artifacts produced by the observability stack at boot:

- `boot.log` — stdout/stderr of `.devcontainer/start_observability.sh`
- `.boot.lock` — process lock to prevent racing boots

**Everything in this directory is gitignored** (except this README and a
`.gitkeep`). The committed source of truth is:

- `observability/docker-compose.observability.yml` — the stack itself
- `observability/grafana/dashboards/*.json` — dashboards
- `observability/{prometheus,loki,tempo,otel-collector}/*.yml` — configs

If you want to inspect the stack:

```bash
tail -f .observability/boot.log
docker compose -f observability/docker-compose.observability.yml ps
```
