# SPDX-License-Identifier: Apache-2.0
"""Universal lock projections; no package install, build, network, or model load.

These checks validate PEP 508 selection, not actual wheel/platform qualification.
"""
from pathlib import Path
import re
import unittest
from packaging.markers import default_environment
from packaging.requirements import Requirement

LOCK = Path(__file__).resolve().parents[1] / "requirements/ci/test.txt"
HAS_UVLOOP = False
HAS_COLORAMA = True
HAS_JSFETCH = True


def records():
    blocks = []
    current = []
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if line and not line[0].isspace() and not line.startswith("#"):
            if current:
                blocks.append(current)
            current = [line]
        elif current and line.strip() and not line.lstrip().startswith("#"):
            current.append(line)
    if current:
        blocks.append(current)
    result = {}
    for block in blocks:
        requirement = Requirement(block[0].rstrip().removesuffix("\\").rstrip())
        if requirement.name in result:
            raise AssertionError("duplicate lock entry: " + requirement.name)
        hashes = re.findall(r"--hash=sha256:([0-9a-f]{64})(?![0-9a-f])", "\n".join(block))
        pins = tuple(requirement.specifier)
        if not hashes or len(pins) != 1 or pins[0].operator != "==" or "*" in pins[0].version:
            raise AssertionError("lock entry must retain exact version and SHA256: " + requirement.name)
        result[requirement.name] = requirement
    if not result:
        raise AssertionError("empty lock")
    return result


def selected(platform, python="3.12", implementation="CPython"):
    env = default_environment()
    env.update(sys_platform=platform, python_version=python,
               python_full_version=python+".0", platform_python_implementation=implementation,
               implementation_name="pypy" if implementation == "PyPy" else "cpython",
               os_name="nt" if platform == "win32" else "posix",
               platform_system="Windows" if platform == "win32" else "Linux")
    return {name for name, req in records().items()
            if req.marker is None or req.marker.evaluate(env)}


class UniversalLockTests(unittest.TestCase):
    def test_exact_versions_and_hashes_remain(self):
        self.assertIn("fastapi", records())

    def test_windows_does_not_select_uvloop(self):
        for version in ("3.11", "3.12", "3.13", "3.14", "3.15"):
            with self.subTest(version=version):
                self.assertNotIn("uvloop", selected("win32", version))

    def test_pypy_does_not_select_uvloop(self):
        self.assertNotIn("uvloop", selected("linux", implementation="PyPy"))

    def test_cygwin_does_not_select_uvloop(self):
        self.assertNotIn("uvloop", selected("cygwin"))

    def test_linux_keeps_intended_uvloop_dependency(self):
        self.assertEqual("uvloop" in selected("linux"), HAS_UVLOOP)

    def test_windows_keeps_pytest_colorama_when_applicable(self):
        self.assertEqual("colorama" in selected("win32"), HAS_COLORAMA)
        self.assertNotIn("colorama", selected("linux"))

    def test_httpx2_browser_transport_is_platform_qualified(self):
        self.assertEqual("httpx2-jsfetch" in selected("emscripten"), HAS_JSFETCH)
        self.assertNotIn("httpx2-jsfetch", selected("emscripten", "3.11"))
        self.assertNotIn("httpx2-jsfetch", selected("linux"))
        self.assertNotIn("httpx2-jsfetch", selected("win32"))
        if HAS_JSFETCH:
            for name in ("h11", "httpcore2", "truststore"):
                with self.subTest(name=name):
                    self.assertNotIn(name, selected("emscripten"))
                    self.assertIn(name, selected("linux"))


if __name__ == "__main__":
    unittest.main()
