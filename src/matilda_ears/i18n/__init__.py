"""
Matilda Ears i18n Module
========================

Internationalization support for Matilda Ears.

Usage:
    from matilda_ears.i18n import t, t_ears, t_common, set_language

    # Ears-specific translation (default domain)
    print(t("modes.listen_once.name"))        # "Listen Once"
    print(t("status.loading_models"))         # "Loading models..."

    # With interpolation
    print(t("errors.mode_not_available", mode="Listen Once", error="No mic"))

    # Common domain (shared terms)
    print(t_common("status.ready"))           # "Ready"
    print(t_common("errors.not_found", item="Model"))

    # Explicit domain
    print(t("cli.name", domain="ears"))       # "Ears"

    # Change language
    set_language("es")
"""

import sys
from pathlib import Path
from typing import Any

# Add central i18n to path for base_loader import
_I18N_PATH = Path("/workspace/i18n")
if _I18N_PATH.exists() and str(_I18N_PATH) not in sys.path:
    sys.path.insert(0, str(_I18N_PATH))

try:
    from base_loader import I18nLoader, get_monorepo_locales_path
except ImportError:
    # Fallback: define minimal loader inline if base not available
    from typing import Callable, Dict, Optional
    import json
    import threading
    import os

    def get_monorepo_locales_path() -> Path:
        for p in [Path("/workspace/i18n/locales"), Path(__file__).parent / "locales"]:
            if p.exists():
                return p
        return Path("/workspace/i18n/locales")

    class I18nLoader:
        def __init__(self, locales_path=None, default_domain="common", default_language="en"):
            self.locales_path = locales_path or get_monorepo_locales_path()
            self.default_domain = default_domain
            self._cache: Dict[str, dict] = {}
            self._lock = threading.Lock()
            self._lang = default_language

        def set_language(self, lang: str): self._lang = lang; self._cache.clear()
        def get_language(self) -> str: return os.environ.get("MATILDA_LANG", self._lang)[:2]

        def _load_domain(self, domain: str, lang: str = None) -> dict:
            lang = lang or self.get_language()
            key = f"{lang}:{domain}"
            with self._lock:
                if key not in self._cache:
                    for try_lang in [lang, "en"]:
                        path = self.locales_path / try_lang / f"{domain}.json"
                        if path.exists():
                            self._cache[key] = json.loads(path.read_text())
                            break
                    else:
                        self._cache[key] = {}
                return self._cache.get(key, {})

        def t(self, key: str, domain: str = None, **kw) -> str:
            domain = domain or self.default_domain
            val = self._load_domain(domain)
            for part in key.split("."):
                val = val.get(part, {}) if isinstance(val, dict) else {}
            if not isinstance(val, str):
                return self.t(key, "common", **kw) if domain != "common" else key
            return val.format(**kw) if kw else val

        def t_domain(self, domain: str) -> Callable[..., str]:
            return lambda key, **kw: self.t(key, domain, **kw)


# =============================================================================
# Ears-specific loader instance
# =============================================================================

_loader = I18nLoader(default_domain="ears")

# Primary translation function (defaults to ears domain)
t = _loader.t

# Domain-specific shortcuts
t_ears = _loader.t_domain("ears")
t_common = _loader.t_domain("common")

# Language management
set_language = _loader.set_language
get_language = _loader.get_language

# Re-export for convenience
__all__ = [
    "t",
    "t_ears",
    "t_common",
    "set_language",
    "get_language",
    "I18nLoader",
]
