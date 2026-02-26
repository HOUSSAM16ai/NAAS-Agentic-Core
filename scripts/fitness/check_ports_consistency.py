"""يفحص اتساق المنافذ بين compose وMakefile ووثيقة مصدر الحقيقة."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTS_FILE = REPO_ROOT / "docs/architecture/PORTS_SOURCE_OF_TRUTH.json"
DOCKER_COMPOSE = REPO_ROOT / "docker-compose.yml"
DOCKER_COMPOSE_LEGACY = REPO_ROOT / "docker-compose.legacy.yml"
MAKEFILE = REPO_ROOT / "Makefile"


def _contains_port(file_path: Path, port: int) -> bool:
    content = file_path.read_text(encoding="utf-8")
    token = f'"{port}:{port}"'
    return token in content or f"localhost:{port}" in content


def main() -> int:
    ports = json.loads(PORTS_FILE.read_text(encoding="utf-8"))
    required_ports = [ports["api_gateway"], ports["core_kernel"]]
    for port in required_ports:
        if not _contains_port(DOCKER_COMPOSE, port):
            print(f"❌ Missing port {port} in docker-compose.yml")
            return 1
        if not _contains_port(DOCKER_COMPOSE_LEGACY, port):
            print(f"❌ Missing port {port} in docker-compose.legacy.yml")
            return 1
        if not _contains_port(MAKEFILE, port):
            print(f"❌ Missing port {port} in Makefile")
            return 1
    print("✅ Port consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
