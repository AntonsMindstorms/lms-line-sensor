"""tools/pybricks_bundle_ast.py: the source-to-source steps behind the bundle."""

import ast
import textwrap

import pytest

import pybricks_bundle_ast as tool

from conftest import REPO_ROOT

SOURCE = textwrap.dedent(
    '''
    class Base:
        MODE_RAW = 0
        MODE_SAVING = 2
        MIN = 9
        POSITION = 8

        def _decode_index(self, raw, idx, invert_values=False):
            """Full version."""
            return raw[idx]

        def _select_indices(self, raw, indices, invert_values=False):
            return raw

        def kept(self):
            """Kept in the bundle."""
            return 1

        def tagged(self):
            """[pybricks:omit] Dropped from the bundle."""
            return 2


    class Client(Base):
        def public(self):
            """Plain public method."""
            return 1

        def tagged_with_text(self):
            """[pybricks:omit] Return something."""
            return 2

        def _private(self):
            return 3

        def tag_not_first(self):
            """Return something.

            [pybricks:omit]
            """
            return 4

        def undocumented(self):
            return 5
    '''
)


class TestOmitTag:
    @staticmethod
    def method(source):
        return ast.parse(textwrap.dedent(source)).body[0]

    def test_tag_alone(self):
        node = self.method('def f():\n    """[pybricks:omit]"""\n')
        assert tool.is_pybricks_omit(node)

    def test_tag_followed_by_text(self):
        node = self.method('def f():\n    """[pybricks:omit] Return the thing."""\n')
        assert tool.is_pybricks_omit(node)

    def test_tag_must_be_on_the_first_line(self):
        node = self.method('def f():\n    """Summary.\n\n    [pybricks:omit]\n    """\n')
        assert not tool.is_pybricks_omit(node)

    def test_tag_must_be_a_whole_word(self):
        node = self.method('def f():\n    """[pybricks:omitted] nope"""\n')
        assert not tool.is_pybricks_omit(node)

    def test_no_docstring(self):
        assert not tool.is_pybricks_omit(self.method("def f():\n    pass\n"))


class TestIntrospection:
    def test_omitted_methods_by_class(self):
        assert tool.pybricks_omit_methods(SOURCE) == ["tagged", "tagged_with_text"]
        assert tool.pybricks_omit_methods(SOURCE, "Base") == ["tagged"]
        assert tool.pybricks_omit_methods(SOURCE, "Client") == ["tagged_with_text"]

    def test_unknown_class_has_no_omitted_methods(self):
        assert tool.pybricks_omit_methods(SOURCE, "Nope") == []

    def test_bundle_methods_are_public_and_untagged(self):
        source = SOURCE.replace("class Client", "class LineSensorUR")
        assert tool.bundle_ur_methods(source) == [
            "public",
            "tag_not_first",
            "undocumented",
        ]

    def test_extract_class_module(self):
        extracted = tool.extract_class_module(SOURCE, "Client")
        assert extracted.startswith("class Client(Base):")
        assert "class Base" not in extracted

    def test_extract_unknown_class(self):
        with pytest.raises(ValueError, match="Nope not found"):
            tool.extract_class_module(SOURCE, "Nope")

    def test_extract_ur_module_starts_at_the_marker(self):
        marker = '"""uRemote transport for the LMS line sensor."""'
        extracted = tool.extract_ur_module("before\n" + marker + "\nclass X: pass\n")
        assert extracted.startswith(marker)
        assert "before" not in extracted

    def test_extract_ur_module_requires_the_marker(self):
        with pytest.raises(ValueError):
            tool.extract_ur_module("no marker here")


class TestTransform:
    def test_plain_transform_keeps_everything(self):
        out = tool.transform_module(SOURCE)
        for name in ("tagged", "tagged_with_text", "_private", "Full version"):
            assert name in out

    def test_omit_tagged_methods(self):
        out = tool.transform_module(SOURCE, omit_tagged_methods=True)
        assert "def tagged(" not in out
        assert "def tagged_with_text(" not in out
        assert "def kept(" in out
        assert "def tag_not_first(" in out

    def test_strip_docstrings_from_methods(self):
        out = tool.transform_module(SOURCE, strip_docstrings=True)
        assert "Kept in the bundle" not in out
        assert "def kept(self):\n        return 1" in out

    def test_stripping_keeps_methods_whose_body_was_only_a_docstring(self):
        out = tool.transform_module("class A:\n    def f(self):\n        'doc'\n")
        assert "def f(self)" in out

    def test_slim_base_removes_unneeded_constants_and_inversion(self):
        out = tool.transform_module(SOURCE.replace("Base", "BaseLineSensor"), slim_base=True)
        assert "MODE_SAVING" not in out
        assert "MIN = 9" not in out
        assert "MODE_RAW = 0" in out
        assert "POSITION = 8" in out
        assert "invert_values" not in out

    def test_slim_only_applies_to_the_base_class(self):
        out = tool.transform_module(SOURCE, slim_base=True)  # class is called Base
        assert "MIN = 9" in out
        assert "invert_values" in out

    def test_output_is_valid_python(self):
        ast.parse(tool.transform_module(SOURCE, omit_tagged_methods=True, slim_base=True))


class TestSlimDecoder:
    """The slim decoder must decode like the full one, minus inversion."""

    @staticmethod
    def build(source):
        namespace = {}
        exec(source, namespace)
        return namespace

    def test_slim_and_full_decoders_agree(self):
        from line_sensor import BaseLineSensor

        namespace = self.build(
            "class S:\n"
            "    VALUES = -1\n    POSITION = 8\n    DERIVATIVE = 11\n    SHAPE = 12\n"
            "    SENSOR_COUNT = 8\n"
            + textwrap.indent(tool._slim_decode_index_source(), "    ")
            + textwrap.indent(tool._slim_select_indices_source(), "    ")
        )
        slim, full = namespace["S"](), BaseLineSensor()
        packet = list(range(10, 22)) + [ord("Y")]
        for indices in [(), (-1,), (8,), (11,), (12,), (9, 10), (12, -1, 8)]:
            assert slim._select_indices(packet, indices) == full._select_indices(packet, indices)


class TestAdaptUrForBundle:
    @pytest.fixture
    def adapted(self):
        source = (REPO_ROOT / "micropython" / "line_sensor.py").read_text(encoding="utf-8")
        return tool.adapt_ur_for_bundle(tool.extract_ur_module(source))

    def test_the_constructor_no_longer_takes_a_remote_class(self, adapted):
        assert "def __init__(self, port=None, settle_ms=1):" in adapted
        assert "remote_class" not in adapted

    def test_the_bundle_uses_the_inlined_uremote(self, adapted):
        assert "from uremote import" not in adapted
        assert "self.ur = uRemote(port) if port else uRemote()" in adapted

    def test_the_wait_fallback_is_removed(self, adapted):
        assert "from time import sleep" not in adapted
        assert "def wait(" not in adapted

    def test_the_class_survives(self, adapted):
        assert "class LineSensorUR(BaseLineSensor):" in adapted
        ast.parse(adapted)
