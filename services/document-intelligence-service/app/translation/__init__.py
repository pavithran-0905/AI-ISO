"""Translation, language detection and terminology preservation."""

from app.translation.translator import (
    Glossary,
    GlossaryEntry,
    LanguageGuess,
    TranslationBackend,
    TranslationConfig,
    TranslationResult,
    TranslationUnavailableError,
    detect_language,
    protect,
    restore,
    translate,
    translate_many,
)

__all__ = [
    "Glossary",
    "GlossaryEntry",
    "LanguageGuess",
    "TranslationBackend",
    "TranslationConfig",
    "TranslationResult",
    "TranslationUnavailableError",
    "detect_language",
    "protect",
    "restore",
    "translate",
    "translate_many",
]
