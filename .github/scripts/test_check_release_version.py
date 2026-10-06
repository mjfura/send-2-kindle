"""Tests for check_release_version.py. Run: python -m unittest discover -s .github/scripts"""

import json
import tempfile
import unittest
from pathlib import Path

from check_release_version import check


class CheckReleaseVersionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def _pyproject(self, version: str) -> Path:
        path = self.dir / "pyproject.toml"
        path.write_text(f'[project]\nversion = "{version}"\n')
        return path

    def _plugin(self, version: str) -> Path:
        path = self.dir / "plugin.json"
        path.write_text(json.dumps({"name": "s2k", "version": version}))
        return path

    def test_matching_manifests_pass(self) -> None:
        self.assertIsNone(check("v0.1.0", [self._pyproject("0.1.0"), self._plugin("0.1.0")]))

    def test_tag_mismatch_fails(self) -> None:
        self.assertIn("does not match", check("v0.1.1", [self._pyproject("0.1.0")]) or "")

    def test_plugin_json_mismatch_fails(self) -> None:
        error = check("v0.1.0", [self._pyproject("0.1.0"), self._plugin("0.0.9")])
        self.assertIn("plugin.json", error or "")

    def test_release_candidate_matches_both_manifests(self) -> None:
        manifests = [self._pyproject("0.2.0rc1"), self._plugin("0.2.0rc1")]
        self.assertIsNone(check("v0.2.0-rc.1", manifests))

    def test_non_canonical_version_fails(self) -> None:
        self.assertIn("not canonical", check("v0.2.0-rc.1", [self._pyproject("0.2.0-rc.1")]) or "")

    def test_invalid_tag_fails(self) -> None:
        self.assertIn("not a valid version", check("vnope", [self._pyproject("0.1.0")]) or "")

    def test_invalid_manifest_version_fails(self) -> None:
        self.assertIn("not a valid version", check("v0.1.0", [self._plugin("latest")]) or "")


if __name__ == "__main__":
    unittest.main()
