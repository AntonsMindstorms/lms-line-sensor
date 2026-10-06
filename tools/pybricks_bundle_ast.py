"""Transform line_sensor sources into a slim Pybricks upload bundle."""

import ast
import textwrap

PYBRICKS_OMIT_TAG = "[pybricks:omit]"

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

BASE_OMIT_CONSTANTS = frozenset({"MODE_SAVING", "MODE_DIGITAL", "MODE_CALIBRATING", "MIN", "MAX"})


def _docstring(node):
    return ast.get_docstring(node, clean=False)


def is_pybricks_omit(node):
    doc = _docstring(node)
    if not doc:
        return False
    first_line = doc.lstrip().split("\n", 1)[0].strip()
    return first_line == PYBRICKS_OMIT_TAG or first_line.startswith(PYBRICKS_OMIT_TAG + " ")


def _strip_function_docstring(node):
    if not node.body:
        return
    first = node.body[0]
    if isinstance(first, ast.Expr):
        value = first.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            node.body = node.body[1:]


def _omit_constant_assign(node):
    if not isinstance(node, ast.Assign):
        return False
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id in BASE_OMIT_CONSTANTS:
            return True
    return False


def _slim_decode_index_source():
    return textwrap.dedent("""
    def _decode_index(self, raw, idx):
        if idx == self.VALUES:
            return tuple(raw[: self.SENSOR_COUNT])
        if idx == self.POSITION or idx == self.DERIVATIVE:
            return raw[idx] - 128
        if idx == self.SHAPE:
            return chr(raw[idx])
        return raw[idx]
    """).strip() + "\n"


def _slim_select_indices_source():
    return textwrap.dedent("""
    def _select_indices(self, raw, indices):
        raw = tuple(raw)
        if not indices:
            return raw

        if len(indices) == 1:
            return self._decode_index(raw, indices[0])

        out = []
        for idx in indices:
            decoded = self._decode_index(raw, idx)
            if idx == self.VALUES:
                out.extend(decoded)
            else:
                out.append(decoded)
        return tuple(out)
    """).strip() + "\n"


def _replace_class_methods(class_node, replacements):
    parsed = {}
    for name, src in replacements.items():
        mod = ast.parse(src)
        parsed[name] = mod.body[0]

    new_body = []
    for item in class_node.body:
        if isinstance(item, FUNCTION_NODES) and item.name in parsed:
            new_body.append(parsed[item.name])
        else:
            new_body.append(item)
    class_node.body = new_body


def transform_module(source, *, omit_tagged_methods=False, slim_base=False, strip_docstrings=False):
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        if slim_base and node.name == "BaseLineSensor":
            node.body = [item for item in node.body if not _omit_constant_assign(item)]
            _replace_class_methods(
                node,
                {
                    "_decode_index": _slim_decode_index_source(),
                    "_select_indices": _slim_select_indices_source(),
                },
            )

        new_body = []
        for item in node.body:
            if isinstance(item, FUNCTION_NODES):
                if omit_tagged_methods and is_pybricks_omit(item):
                    continue
                if strip_docstrings:
                    _strip_function_docstring(item)
            new_body.append(item)
        node.body = new_body

    return ast.unparse(tree)


def pybricks_omit_methods(source, class_name=None):
    omitted = []
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if class_name and node.name != class_name:
                continue
            for item in node.body:
                if isinstance(item, FUNCTION_NODES) and is_pybricks_omit(item):
                    omitted.append(item.name)
    return omitted


def bundle_ur_methods(source):
    methods = []
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "LineSensorUR":
            for item in node.body:
                if isinstance(item, FUNCTION_NODES) and not item.name.startswith("_"):
                    if not is_pybricks_omit(item):
                        methods.append(item.name)
    return methods


def extract_class_module(source, class_name):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return ast.unparse(node)
    raise ValueError(f"{class_name} not found in source")


def extract_ur_module(source):
    marker = '"""uRemote transport for the LMS line sensor."""'
    idx = source.index(marker)
    return source[idx:].strip()


def adapt_ur_for_bundle(source):
    lines = []
    slines = source.splitlines()
    i = 0
    while i < len(slines):
        line = slines[i]
        stripped = line.strip()
        if stripped == "from .base import BaseLineSensor":
            i += 1
            continue
        if stripped == "try:" and i + 1 < len(slines) and "pybricks.tools import wait" in slines[i + 1]:
            i += 1
            while i < len(slines) and not slines[i].strip().startswith("class LineSensorUR"):
                i += 1
            continue
        lines.append(line)
        i += 1

    # uRemote and uRemoteError are module globals in the bundle.
    return "\n".join(line for line in lines if line.strip() != "from uremote import uRemote, uRemoteError")


UREMOTE_SERVER_ONLY = frozenset({"process", "_send_command", "_recv_command"})
UREMOTE_ESP32_ARGS = frozenset({"rx", "tx"})


class _PybricksOnly(ast.NodeTransformer):
    """Fold ``_IS_PYBRICKS`` to True and drop the ESP32 branches."""

    def _truth(self, test):
        if isinstance(test, ast.Name) and test.id == "_IS_PYBRICKS":
            return True
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            inner = self._truth(test.operand)
            return None if inner is None else not inner
        if isinstance(test, ast.Compare) and isinstance(test.left, ast.Constant):
            if test.left.value == "Pybricks":
                return True
        return None

    def visit_If(self, node):
        self.generic_visit(node)
        truth = self._truth(node.test)
        if truth is None:
            return node
        return (node.body if truth else node.orelse) or None

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.And):
            values = [v for v in node.values if self._truth(v) is not True]
            if len(values) == 1:
                return values[0]
            node.values = values
        return node


def _is_dunder_or_platform_assign(node):
    if not isinstance(node, ast.Assign):
        return False
    names = [t.id for t in node.targets if isinstance(t, ast.Name)]
    return any(n.startswith("__") or n == "_IS_PYBRICKS" for n in names)


def _is_optional_import(node):
    # try: from micropython import const / from lms_esp32 import RX_PIN
    if not isinstance(node, ast.Try):
        return False
    first = node.body[0]
    return isinstance(first, ast.ImportFrom) and first.module in {"micropython", "lms_esp32"}


def _drop_args(func, names):
    args = func.args
    first_default = len(args.args) - len(args.defaults)
    kept, defaults = [], []
    for i, arg in enumerate(args.args):
        if arg.arg in names:
            continue
        kept.append(arg)
        if i >= first_default:
            defaults.append(args.defaults[i - first_default])
    args.args, args.defaults = kept, defaults


def trim_uremote_for_pybricks(source):
    """Return the Pybricks client part of upstream ``uremote.py``.

    Drops the ESP32 branches, the server side, dunder metadata and
    docstrings, so the bundle stays small while the transport logic lives
    only in the uRemote submodule.
    """
    tree = _PybricksOnly().visit(ast.parse(source))
    body = [ast.parse("def const(value):\n    return value").body[0]]
    for node in tree.body:
        if isinstance(node, ast.Import):
            continue
        if _is_optional_import(node) or _is_dunder_or_platform_assign(node):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, ast.ClassDef):
            _strip_function_docstring(node)
            node.body = [
                item for item in node.body
                if not (isinstance(item, FUNCTION_NODES) and item.name in UREMOTE_SERVER_ONLY)
            ]
            for item in node.body:
                if isinstance(item, FUNCTION_NODES):
                    _strip_function_docstring(item)
                    if item.name == "__init__":
                        _drop_args(item, UREMOTE_ESP32_ARGS)
        body.append(node)
    tree.body = body
    return ast.unparse(ast.fix_missing_locations(tree))
