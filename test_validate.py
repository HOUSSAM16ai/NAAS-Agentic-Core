from pathlib import Path
import json
payload = {
  "pull_request": {
    "title": "refactor(telemetry): Add debug logging to silenced exception in retrieval",
    "body": Path("pr_desc.md").read_text()
  }
}
Path("/tmp/payload.json").write_text(json.dumps(payload))
