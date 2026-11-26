#!/usr/bin/env python3
"""Keep bounded evidence from a completed disposable browser assertion."""

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path

LOG_LIMIT = 4096
FILE_LIMIT = 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def bounded_file(directory_fd, name, limit, *, truncate=False):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=directory_fd)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"{name} must be a regular input file")
        data = stream.read(limit + 1)
    excess = len(data) > limit
    if excess and not truncate:
        raise ValueError(f"{name} exceeds its evidence limit")
    return data[:limit], excess


def describe(name, data):
    return {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def collect(args):
    inputs = os.open(args.inputs, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        artifact, _ = bounded_file(inputs, "app.html", FILE_LIMIT)
        log, truncated = bounded_file(inputs, "browser.log", LOG_LIMIT, truncate=True)
        screenshot, _ = bounded_file(inputs, "screenshot.png", FILE_LIMIT)
    finally:
        os.close(inputs)
    if not artifact or not screenshot.startswith(PNG_SIGNATURE):
        raise ValueError("Expected a nonempty application artifact and a PNG screenshot")

    report = {
        "schema": 1,
        "run_id": args.run_id,
        "generation": args.generation,
        "platform": args.platform,
        "browser": args.browser,
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "exit_code": args.exit_code,
        "result": "pass" if args.exit_code == 0 else "failure",
        "log": {**describe("browser.log", log), "truncated": truncated},
        "screenshot": describe("screenshot.png", screenshot),
    }
    # A completed manifest appears only after both retained files are present.
    args.output.mkdir(mode=0o700, exist_ok=False)
    (args.output / "browser.log").write_bytes(log)
    (args.output / "screenshot.png").write_bytes(screenshot)
    pending = args.output / ".evidence.json"
    pending.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pending.replace(args.output / "evidence.json")
    return args.exit_code


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--browser", required=True)
    parser.add_argument("--exit-code", required=True, type=int)
    args = parser.parse_args()
    labels = (args.run_id, args.generation, args.platform, args.browser)
    if not all(label.strip() and len(label) <= 160 for label in labels):
        parser.error("Evidence labels must contain 1 to 160 characters")
    if not 0 <= args.exit_code <= 255:
        parser.error("Browser exit status must be from 0 to 255")
    try:
        return collect(args)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Could not collect browser evidence: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
