"""Vercel serverless entry — loads RedirectHandler from custom-redirect-script.py unchanged."""
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "custom-redirect-script.py"

_spec = importlib.util.spec_from_file_location("custom_redirect_script", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["custom_redirect_script"] = _mod
_spec.loader.exec_module(_mod)


class handler(_mod.RedirectHandler):
    """Vercel's Python runtime expects this name for http.server-style functions."""
