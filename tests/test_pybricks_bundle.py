"""The generated, standalone Pybricks driver (micropython/line_sensor_pybricks.py)."""

import ast

import pytest

import line_sensor
import line_sensor_pybricks as bundle
import pybricks_bundle_ast as tool
from generate_line_sensor_pybricks import OUTPUT_FILE, build_bundle

from conftest import REPO_ROOT

LINE_SENSOR_SOURCE = (REPO_ROOT / "micropython" / "line_sensor.py").read_text(encoding="utf-8")
BUNDLE_SOURCE = OUTPUT_FILE.read_text(encoding="utf-8")

# Pybricks hubs load slowly from the app; the bundle was trimmed on purpose.
SIZE_BUDGET_BYTES = 20_000


def test_committed_bundle_is_up_to_date():
    assert BUNDLE_SOURCE == build_bundle(), (
        "line_sensor_pybricks.py is stale; run: python tools/generate_line_sensor_pybricks.py"
    )


def test_bundle_is_marked_as_generated():
    assert "Do not edit by hand" in BUNDLE_SOURCE.split('"""')[1]


def test_bundle_stays_small():
    assert len(BUNDLE_SOURCE.encode()) < SIZE_BUDGET_BYTES


def test_exported_names_exist():
    assert set(bundle.__all__) == {
        "BaseLineSensor",
        "LineSensorUR",
        "uRemote",
        "uRemoteError",
        "__version__",
    }
    for name in bundle.__all__:
        assert hasattr(bundle, name), name


class TestSelfContained:
    """Every ``self.method()`` the bundle calls must exist in the bundle."""

    @staticmethod
    def self_calls(class_node):
        called, assigned = set(), set()
        for node in ast.walk(class_node):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
            ):
                called.add(node.func.attr)
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                if isinstance(node.value, ast.Name) and node.value.id == "self":
                    assigned.add(node.attr)
        return called - assigned

    @pytest.mark.parametrize("name", ["BaseLineSensor", "LineSensorUR", "uRemote"])
    def test_calls_resolve(self, name):
        class_node = next(
            node
            for node in ast.parse(BUNDLE_SOURCE).body
            if isinstance(node, ast.ClassDef) and node.name == name
        )
        # The base class is abstract: its helpers call what LineSensorUR defines.
        cls = bundle.LineSensorUR if name == "BaseLineSensor" else getattr(bundle, name)
        missing = sorted(m for m in self.self_calls(class_node) if not hasattr(cls, m))
        assert not missing, "%s calls methods that are not in the bundle: %s" % (name, missing)

    def test_version_matches_the_full_driver(self):
        assert bundle.__version__ == line_sensor.__version__


class TestTrimming:
    def omitted(self, class_name):
        return tool.pybricks_omit_methods(LINE_SENSOR_SOURCE, class_name)

    @pytest.mark.parametrize("class_name", ["BaseLineSensor", "LineSensorUR"])
    def test_tagged_methods_are_not_in_the_bundle(self, class_name):
        cls = getattr(bundle, class_name)
        for method in self.omitted(class_name):
            assert method not in vars(cls), "%s.%s should be omitted" % (class_name, method)

    def test_expected_methods_are_omitted(self):
        assert {"ping", "debug", "uid_hex"} <= set(
            self.omitted("LineSensorUR") + self.omitted("BaseLineSensor")
        )

    def test_untagged_public_methods_are_all_present(self):
        for method in tool.bundle_ur_methods(LINE_SENSOR_SOURCE):
            assert method in vars(bundle.LineSensorUR), method

    @pytest.mark.parametrize("name", ["BaseLineSensor", "LineSensorUR"])
    def test_docstrings_are_stripped_from_the_line_sensor_classes(self, name):
        class_node = next(
            node
            for node in ast.parse(BUNDLE_SOURCE).body
            if isinstance(node, ast.ClassDef) and node.name == name
        )
        for node in ast.walk(class_node):
            if isinstance(node, ast.FunctionDef):
                assert ast.get_docstring(node) is None, "%s.%s" % (name, node.name)

    def test_the_slim_base_drops_unused_constants(self):
        for name in ("MODE_SAVING", "MODE_DIGITAL", "MODE_CALIBRATING", "MIN", "MAX"):
            assert not hasattr(bundle.BaseLineSensor, name), name
        for name in ("MODE_RAW", "MODE_CALIBRATED", "POSITION", "SHAPE", "VALUES"):
            assert getattr(bundle.BaseLineSensor, name) == getattr(line_sensor.BaseLineSensor, name)

    def test_no_i2c_code_in_the_bundle(self):
        assert not hasattr(bundle, "LineSensorI2C")
        assert "machine" not in BUNDLE_SOURCE


class TestDecodingMatchesTheFullDriver:
    PACKET = [10, 20, 30, 40, 50, 60, 70, 80, 200, 5, 90, 100, ord("T")]

    @pytest.mark.parametrize(
        "indices",
        [(), (-1,), (8,), (11,), (12,), (8, 11, 12), (12, -1)],
    )
    def test_select_indices(self, indices):
        slim = bundle.BaseLineSensor()
        full = line_sensor.BaseLineSensor()
        assert slim._select_indices(self.PACKET, indices) == full._select_indices(
            self.PACKET, indices
        )

    def test_the_bundle_never_inverts_values(self):
        slim = bundle.BaseLineSensor()
        assert slim._select_indices(self.PACKET, (-1,)) == tuple(self.PACKET[:8])


def test_bundled_uremote_refuses_blocking_calls_under_run_task(monkeypatch, bench):
    bench.link("uart1", "portB")
    monkeypatch.setattr(bundle, "run_task", lambda: True)
    remote = bundle.uRemote("B")
    with pytest.raises(bundle.uRemoteError, match="call_async"):
        remote.call("all")
    assert bench.endpoint("portB").peer.rx == b""
