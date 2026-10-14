"""Smoke tests for the installed fingerprint-sampler (STORY-FING-41).

Run by `make smoke` against the built wheel in a throwaway environment. Kept deliberately
small: the installed command starts, and the README's examples work as written. Behaviour
belongs in the unit tests under tests/, not here.
"""

import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(PACKAGE_ROOT, "README.md")


def fingerprint(*args, cwd=None):
    return subprocess.run(
        ["fingerprint", *args], cwd=cwd, capture_output=True, text=True, timeout=60
    )


def readme_section(heading):
    """The README text under `## heading`, up to the next `## ` heading."""
    with open(README, encoding="utf-8") as f:
        text = f.read()
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"README has no '## {heading}' section")
    return match.group(1)


def fenced_blocks(text, language):
    """Bodies of the ``` blocks with exactly this info string ('' for an unlabelled block)."""
    blocks, body, info = [], None, None
    for line in text.splitlines(keepends=True):
        if body is None and line.startswith("```"):
            body, info = [], line[3:].strip()
        elif body is not None and line.rstrip("\n") == "```":
            if info == language:
                blocks.append("".join(body))
            body = None
        elif body is not None:
            body.append(line)
    return blocks


class InstalledCommandTests(unittest.TestCase):
    def test_version_matches_the_package_version(self):
        with open(os.path.join(PACKAGE_ROOT, "pyproject.toml"), "rb") as f:
            version = tomllib.load(f)["project"]["version"]
        result = fingerprint("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"fingerprint-sampler {version}")


class ReadmeTests(unittest.TestCase):
    """The README's examples, run exactly as a reader would run them."""

    def run_quickstart(self, tmp):
        section = readme_section("Quickstart")
        script = fenced_blocks(section, "sh")[0]
        result = subprocess.run(
            ["bash", "-e", "-c", script], cwd=tmp, capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return section, result

    def test_quickstart_prints_the_output_it_shows(self):
        # The history file is named by the time of the run, so any run time matches.
        def any_run_time(text):
            return re.sub(r"\d{4}-\d\d-\d\dT\d{6}Z(_\d+)?\.yaml", "<run time>.yaml", text)

        with tempfile.TemporaryDirectory() as tmp:
            section, result = self.run_quickstart(tmp)
            expected = fenced_blocks(section, "")[0]
            self.assertEqual(any_run_time(result.stdout + result.stderr), any_run_time(expected))

    def test_library_examples_run(self):
        blocks = fenced_blocks(readme_section("As a library"), "python")
        self.assertTrue(blocks)
        with tempfile.TemporaryDirectory() as tmp:
            self.run_quickstart(tmp)  # the first example loads the quickstart's profile.yaml
            for block in blocks:
                with self.subTest(block=block.splitlines()[0]):
                    result = subprocess.run(
                        [sys.executable, "-c", block],
                        cwd=tmp,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
