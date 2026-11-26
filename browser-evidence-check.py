#!/usr/bin/env python3
"""Validate retained ROOT-24 schema 1 browser evidence."""

import argparse
import hashlib
import json
import os
import re
import stat
import sys


JSON_LIMIT = 64 * 1024
LOG_LIMIT = 4096
SCREENSHOT_LIMIT = 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceError(ValueError):
    pass


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def read_regular(directory, name, limit):
    path = os.path.join(directory, name)
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode):
        raise EvidenceError(f"{name} is not a regular file")
    if before.st_size > limit:
        raise EvidenceError(f"{name} exceeds its size limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as file:
        opened = os.fstat(file.fileno())
        if not stat.S_ISREG(opened.st_mode):
            raise EvidenceError(f"{name} is not a regular file")
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise EvidenceError(f"{name} changed while opening")
        data = file.read(limit + 1)
    if len(data) > limit:
        raise EvidenceError(f"{name} exceeds its size limit")
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise EvidenceError(f"invalid JSON constant: {value}")


def require_sha256(value, field):
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise EvidenceError(f"invalid {field}")


def check_file(directory, evidence, key, name, limit):
    entry = evidence.get(key)
    if not isinstance(entry, dict) or entry.get("path") != name:
        raise EvidenceError(f"invalid {key} path")
    size = entry.get("bytes")
    if type(size) is not int or not 0 <= size <= limit:
        raise EvidenceError(f"invalid {key} byte count")
    require_sha256(entry.get("sha256"), f"{key} sha256")
    if key == "log" and type(entry.get("truncated")) is not bool:
        raise EvidenceError("invalid log truncated flag")
    data = read_regular(directory, name, limit)
    if len(data) != size or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise EvidenceError(f"{name} does not match its recorded bytes and sha256")
    if key == "screenshot" and not data.startswith(PNG_SIGNATURE):
        raise EvidenceError("screenshot.png has an invalid PNG signature")


def validate(directory):
    raw = read_regular(directory, "evidence.json", JSON_LIMIT)
    evidence = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant)
    if not isinstance(evidence, dict):
        raise EvidenceError("evidence.json must contain an object")
    if type(evidence.get("schema")) is not int or evidence["schema"] != 1:
        raise EvidenceError("unsupported evidence schema")
    for key in ("run_id", "generation", "platform", "browser"):
        if not isinstance(evidence.get(key), str) or not evidence[key]:
            raise EvidenceError(f"invalid {key}")
    require_sha256(evidence.get("artifact_sha256"), "artifact_sha256")
    exit_code = evidence.get("exit_code")
    if type(exit_code) is not int or not 0 <= exit_code <= 255:
        raise EvidenceError("invalid exit_code")
    if evidence.get("result") != ("pass" if exit_code == 0 else "failure"):
        raise EvidenceError("result does not match exit_code")
    check_file(directory, evidence, "log", "browser.log", LOG_LIMIT)
    check_file(directory, evidence, "screenshot", "screenshot.png", SCREENSHOT_LIMIT)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, help="directory containing retained evidence")
    args = parser.parse_args()
    try:
        validate(args.directory)
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        print(f"Invalid browser evidence: {error}", file=sys.stderr)
        return 1
    print("Browser evidence is valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
