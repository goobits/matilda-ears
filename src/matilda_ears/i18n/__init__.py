"""Matilda Ears i18n Module
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

from matilda_i18n import I18nLoader

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
    "I18nLoader",
    "get_language",
    "set_language",
    "t",
    "t_common",
    "t_ears",
]
