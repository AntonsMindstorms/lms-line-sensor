"""Repository hygiene: things that drift when files are edited by hand."""

import ast
import re
import warnings
from pathlib import Path
from urllib.parse import unquote

import pytest

import fakes
import line_sensor
import line_sensor_pybricks
import line_sensor_ur_server

from conftest import REPO_ROOT

SKIPPED_DIRS = {".git", ".venv", "dist", "node_modules", "__pycache__", "_build"}


def tracked(*patterns):
    found = []
    for pattern in patterns:
        for path in REPO_ROOT.rglob(pattern):
            relative = path.relative_to(REPO_ROOT)
            if not SKIPPED_DIRS.intersection(relative.parts):
                found.append(path)
    return sorted(found)


class TestFirmwareVersion:
    """One firmware release is documented everywhere, and its UF2 is present."""

    @staticmethod
    def current():
        text = (REPO_ROOT / "firmware" / "README.md").read_text(encoding="utf-8")
        match = re.search(r"Current firmware version: \*\*(\d+\.\d+)\*\*", text)
        assert match, "firmware/README.md must state the current firmware version"
        return match.group(1)

    def test_the_matching_uf2_exists_and_is_the_only_one(self):
        uf2 = sorted(p.name for p in (REPO_ROOT / "firmware").glob("*.uf2"))
        assert uf2 == ["firmware_ch32_line_i2c_ur_v%s.uf2" % self.current()]

    @pytest.mark.parametrize(
        "path",
        [
            "README.md",
            "docs/index.rst",
            "docs/API/lms-line-sensor-i2c-api.rst",
            "docs/API/lms-line-sensor-uremote-api.rst",
            "web/README.md",
        ],
    )
    def test_documents_name_the_current_version(self, path):
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert re.search(r"\b%s\b" % re.escape(self.current()), text), path

    def test_no_document_links_to_another_uf2(self):
        names = set()
        for path in tracked("*.md", "*.rst"):
            names.update(re.findall(r"firmware_ch32_line_i2c_ur_v[\d.]+\.uf2", path.read_text(encoding="utf-8")))
        assert names <= {"firmware_ch32_line_i2c_ur_v%s.uf2" % self.current()}

    def test_the_simulated_sensor_reports_the_current_version(self):
        major, minor = fakes.FakeLineSensor.FIRMWARE_VERSION
        assert "%d.%d" % (major, minor) == self.current()


LINK = re.compile(r"\]\((?:<([^>]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\)")


def markdown_links():
    for path in tracked("*.md"):
        for match in LINK.finditer(path.read_text(encoding="utf-8")):
            target = match.group(1) or match.group(2)
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            yield pytest.param(path, target, id="%s -> %s" % (path.relative_to(REPO_ROOT), target))


@pytest.mark.parametrize("source, target", list(markdown_links()))
def test_relative_markdown_links_resolve(source, target):
    destination = unquote(target.split("#", 1)[0].split("?", 1)[0])
    assert (source.parent / destination).exists(), "%s links to missing %s" % (source, target)


@pytest.mark.parametrize(
    "path", tracked("*.py"), ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_python_sources_compile_without_warnings(path):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


EXPORTS = {
    "line_sensor": line_sensor,
    "line_sensor_pybricks": line_sensor_pybricks,
    "line_sensor_ur_server": line_sensor_ur_server,
}


def example_imports():
    for path in tracked("*.py"):
        if "examples" not in path.relative_to(REPO_ROOT).parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module in EXPORTS:
                for alias in node.names:
                    yield pytest.param(
                        node.module,
                        alias.name,
                        id="%s: %s.%s" % (path.relative_to(REPO_ROOT), node.module, alias.name),
                    )


@pytest.mark.parametrize("module, name", list(example_imports()))
def test_examples_import_names_that_exist(module, name):
    assert hasattr(EXPORTS[module], name)


def test_package_version_comes_from_the_driver():
    """pyproject.toml reads the version from ``line_sensor.__version__``."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = { attr = "line_sensor.__version__" }' in pyproject
    assert re.fullmatch(r"\d+\.\d+\.\d+", line_sensor.__version__)
