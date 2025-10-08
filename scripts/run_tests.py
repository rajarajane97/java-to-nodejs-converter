import argparse
import os
import sys
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser(description="Test runner for Java2NodeAI")
    parser.add_argument("--suite", choices=["unit", "all"], default="all")
    parser.add_argument("--keyword", help="pytest -k expression", default=None)
    args = parser.parse_args()

    cmd = [sys.executable, "-m", "pytest", "-q", "--maxfail=1", "--disable-warnings"]
    if args.suite == "unit":
        cmd += ["tests"]
    else:
        cmd += ["tests"]
    if args.keyword:
        cmd += ["-k", args.keyword]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())


