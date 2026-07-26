"""
Internationalization (i18n) support using gettext.

English is the source language (strings in code). Translations are one-way:
only non-English languages need .po/.mo files. When language is "en" or a
translation is missing, the original English string is returned as-is.
"""

import gettext
from pathlib import Path

LOCALE_DIR = Path(__file__).resolve().parent.parent / "locales"
DOMAIN = "prewarning"

_translation: gettext.GNUTranslations | gettext.NullTranslations = (
    gettext.NullTranslations()
)


def set_language(lang: str) -> None:
    """Activate the given language. Use 'en' for English (no-op/fallback)."""
    global _translation
    if lang == "en":
        _translation = gettext.NullTranslations()
    else:
        _translation = gettext.translation(
            DOMAIN, localedir=LOCALE_DIR, languages=[lang], fallback=True
        )


def _(message: str) -> str:
    """Translate a string using the current language."""
    return _translation.gettext(message)


def N_(message: str) -> str:
    """Mark a string for extraction without translating it.

    Use this for strings that are translated later via _() at display time
    (e.g. ConfigOptionDefinition display_name and description).
    """
    return message
