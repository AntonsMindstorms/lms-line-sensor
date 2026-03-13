import os
import sys

sys.path.insert(0, os.path.abspath("../micropython"))

from line_sensor import __version__

project = "LMS Line Sensor"
copyright = "2026"
author = "LMS Line Sensor contributors"
release = __version__
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autodoc_mock_imports = ["machine"]
autodoc_member_order = "bysource"
napoleon_google_docstring = True
napoleon_numpy_docstring = False

html_theme = "alabaster"
html_static_path = ["_static"]
