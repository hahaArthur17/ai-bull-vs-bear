"""Mount the real React application against an isolated, deterministic API."""

import subprocess

from local_review import ROOT, review_api

if __name__ == "__main__":
    with review_api() as environment:
        result = subprocess.run(
            ["npm", "run", "test:ui"],
            cwd=ROOT / "apps/mobile",
            env=environment,
            check=False,
        )
    raise SystemExit(result.returncode)
