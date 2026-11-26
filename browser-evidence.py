#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

MAX_ARTIFACT = 1024 * 1024
MAX_LOG = 4096
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def read_regular(path, limit, allow_truncation=False):
    flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
    # Check explicitly as well on platforms without O_NOFOLLOW.
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f'not a regular input file: {path}')
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError(f'input changed or is not regular: {path}')
        with os.fdopen(fd, 'rb') as stream:
            fd = -1
            data = stream.read(limit + 1)
    finally:
        if fd != -1:
            os.close(fd)
    truncated = len(data) > limit
    if truncated and not allow_truncation:
        raise ValueError(f'input exceeds {limit} bytes: {path}')
    return data[:limit], truncated


def digest(data):
    return hashlib.sha256(data).hexdigest()


def exit_code(value):
    try:
        number = int(value, 10)
    except ValueError:
        raise argparse.ArgumentTypeError('exit code must be an integer from 0 to 255')
    if not 0 <= number <= 255:
        raise argparse.ArgumentTypeError('exit code must be an integer from 0 to 255')
    return number


def main():
    parser = argparse.ArgumentParser(description='Collect browser-test evidence')
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--generation', required=True)
    parser.add_argument('--platform', required=True)
    parser.add_argument('--browser', required=True)
    parser.add_argument('--exit-code', required=True, type=exit_code)
    args = parser.parse_args()

    try:
        inputs_stat = os.lstat(args.inputs)
        if not stat.S_ISDIR(inputs_stat.st_mode):
            raise ValueError('inputs must be a non-symlink directory')
        app, _ = read_regular(args.inputs / 'app.html', MAX_ARTIFACT)
        log, truncated = read_regular(args.inputs / 'browser.log', MAX_LOG, True)
        screenshot, _ = read_regular(args.inputs / 'screenshot.png', MAX_ARTIFACT)
        if not screenshot.startswith(PNG_SIGNATURE):
            raise ValueError('screenshot.png has an invalid PNG signature')

        manifest = {
            'schema': 1,
            'run_id': args.run_id,
            'generation': args.generation,
            'platform': args.platform,
            'browser': args.browser,
            'artifact_sha256': digest(app),
            'exit_code': args.exit_code,
            'result': 'pass' if args.exit_code == 0 else 'failure',
            'log': {
                'path': 'browser.log',
                'bytes': len(log),
                'truncated': truncated,
                'sha256': digest(log),
            },
            'screenshot': {
                'path': 'screenshot.png',
                'bytes': len(screenshot),
                'sha256': digest(screenshot),
            },
        }
        encoded_manifest = (json.dumps(manifest, ensure_ascii=True, indent=2) + '\n').encode('utf-8')

        # mkdir is atomic and refuses existing files, directories and symlinks.
        os.mkdir(args.output, 0o700)
        for name, data in (('browser.log', log), ('screenshot.png', screenshot), ('evidence.json', encoded_manifest)):
            with open(args.output / name, 'xb') as stream:
                stream.write(data)
    except (OSError, ValueError) as exc:
        print(f'browser-evidence: {exc}', file=sys.stderr)
        return 1
    return args.exit_code


if __name__ == '__main__':
    sys.exit(main())
