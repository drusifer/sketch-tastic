"""Smoke tests for the installed fingerprint-sampler (STORY-FING-41).

Run by `make smoke`, which installs the built wheel into a throwaway environment and runs
this suite there: the `fingerprint` command and `fingerprint_sampler` package under test are
the installed ones, not the source tree. The README is executed as written.
"""

import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(PACKAGE_ROOT))
README = os.path.join(PACKAGE_ROOT, "README.md")
EXAMPLE_PROFILES = [
    os.path.join(PACKAGE_ROOT, "examples", "access_log.yaml"),
    os.path.join(REPO_ROOT, "examples", "profiles", "ebpf_telemetry.yaml"),
]


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
    def test_runs_the_installed_package_not_the_source_tree(self):
        import fingerprint_sampler

        self.assertNotIn(PACKAGE_ROOT, os.path.abspath(fingerprint_sampler.__file__))

    def test_version_matches_the_package_version(self):
        with open(os.path.join(PACKAGE_ROOT, "pyproject.toml"), "rb") as f:
            version = tomllib.load(f)["project"]["version"]
        result = fingerprint("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"fingerprint-sampler {version}")

    def test_shipped_example_profiles_check_ok(self):
        result = fingerprint("check", *EXAMPLE_PROFILES)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout.splitlines(), [f"{p}: OK" for p in EXAMPLE_PROFILES])

    def test_invalid_profile_is_refused_by_check_and_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = os.path.join(tmp, "bad.yaml")
            with open(profile, "w") as f:
                f.write('fields:\n  - {key: s, path: $.s, modifier: "IN_RANGE(200, 399)"}\n')
            events = os.path.join(tmp, "events.jsonl")
            with open(events, "w") as f:
                f.write('{"s": 200}\n')

            check = fingerprint("check", profile)
            self.assertEqual(check.returncode, 1)
            self.assertIn(f"{profile}: fields[0] (key 's') → modifier:", check.stdout)

            set_path = os.path.join(tmp, "set.yaml")
            merge = fingerprint("merge", "-p", profile, "-s", set_path, events)
            self.assertEqual(merge.returncode, 2)
            self.assertFalse(os.path.exists(set_path))


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
        with tempfile.TemporaryDirectory() as tmp:
            section, result = self.run_quickstart(tmp)
            expected = fenced_blocks(section, "")[0]
            self.assertEqual(result.stdout + result.stderr, expected)

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

    def test_whole_profiles_in_the_readme_pass_check(self):
        with open(README, encoding="utf-8") as f:
            profiles = [b for b in fenced_blocks(f.read(), "yaml") if re.search(r"^fields:", b, re.M)]
        self.assertTrue(profiles)
        with tempfile.TemporaryDirectory() as tmp:
            for i, body in enumerate(profiles):
                path = os.path.join(tmp, f"readme_{i}.yaml")
                with open(path, "w") as f:
                    f.write(body)
                with self.subTest(profile=i):
                    result = fingerprint("check", path)
                    self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
