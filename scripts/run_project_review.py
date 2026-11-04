"""Start the complete local review profile: python scripts/run_project_review.py.

Uses simulated data with the V2 workflow enabled. Production deployment flags
remain explicit because enabling live workers also requires hosted migrations,
provider configuration and operational acceptance.
"""

import argparse
import subprocess

from local_review import ROOT, free_port, python_executable, review_api, stop_process


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=8017)
    parser.add_argument("--web-port", type=int, default=8097)
    args = parser.parse_args()
    web_port = free_port(args.web_port)
    with review_api(args.api_port, web_port) as environment:
        subprocess.run(
            ["npm", "run", "build:web"], cwd=ROOT / "apps/mobile", env=environment, check=True
        )
        web = subprocess.Popen(
            [
                python_executable(),
                "-m",
                "http.server",
                str(web_port),
                "--bind",
                "127.0.0.1",
                "--directory",
                str(ROOT / "apps/mobile/dist"),
            ]
        )
        try:
            print(
                f"Local simulated review: http://127.0.0.1:{web_port} (Ctrl+C to stop)", flush=True
            )
            web.wait()
        except KeyboardInterrupt:
            pass
        finally:
            stop_process(web)


if __name__ == "__main__":
    main()
