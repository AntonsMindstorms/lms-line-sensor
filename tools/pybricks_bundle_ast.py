"""Transform line_sensor sources into a slim Pybricks upload bundle."""

import ast
import re
import textwrap

PYBRICKS_OMIT_TAG = "[pybricks:omit]"

BASE_OMIT_CONSTANTS = frozenset({"MODE_SAVING", "MODE_CALIBRATING", "MIN", "MAX"})


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
        if isinstance(item, ast.FunctionDef) and item.name in parsed:
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
            if isinstance(item, ast.FunctionDef):
                if omit_tagged_methods and is_pybricks_omit(item):
                    continue
                if strip_docstrings:
                    _strip_function_docstring(item)
            new_body.append(item)
        node.body = new_body

    return ast.unparse(tree)


def pybricks_omit_methods(source):
    omitted = []
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and is_pybricks_omit(item):
                    omitted.append(item.name)
    return omitted


def bundle_ur_methods(source):
    methods = []
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "LineSensorUR":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    if not is_pybricks_omit(item):
                        methods.append(item.name)
    return methods


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

    text = "\n".join(lines)
    init_pattern = r"    def __init__\(self, port=None, settle_ms=1, remote_class=None\):.*?(?=\n    def )"
    bundle_init = """    def __init__(self, port=None, settle_ms=1):
        self.ur = uRemote(port) if port else uRemote()
        self.settle_ms = settle_ms
        config = self.show_config()
        self.version = (config[self.CONFIG_MAJ_VERSION], config[self.CONFIG_MIN_VERSION])
        self.cal_duration = config[self.CONFIG_CAL_DURATION]

"""
    return re.sub(init_pattern, bundle_init, text, count=1, flags=re.DOTALL)
