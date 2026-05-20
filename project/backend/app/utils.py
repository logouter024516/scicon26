from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
import re
import logging

try:
    from deep_translator import GoogleTranslator
except Exception:  # pragma: no cover
    GoogleTranslator = None  # type: ignore[assignment]

_HANGUL_RE = re.compile(r'[\uac00-\ud7a3]')
_TRANSLATOR: GoogleTranslator | None = None
_TRANSLATE_LOGGER = logging.getLogger('missingfind.translate')


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def contains_hangul(text: str) -> bool:
    return bool(_HANGUL_RE.search(text))


def translate_ko_to_en(text: str) -> str:
    if not text or not contains_hangul(text):
        return text
    if GoogleTranslator is None:
        try:
            _TRANSLATE_LOGGER.info('translation: "%s" -> "%s"', text, text)
            _TRANSLATE_LOGGER.warning('translation backend unavailable')
        except Exception:
            pass
        return text
    global _TRANSLATOR
    if _TRANSLATOR is None:
        try:
            _TRANSLATOR = GoogleTranslator(source='ko', target='en')
        except Exception:
            try:
                _TRANSLATE_LOGGER.info('translation: "%s" -> "%s"', text, text)
                _TRANSLATE_LOGGER.warning('translator init failed')
            except Exception:
                pass
            return text
    try:
        translated = str(_TRANSLATOR.translate(text)).strip()
        final = translated or text
        try:
            _TRANSLATE_LOGGER.info('translation: "%s" -> "%s"', text, final)
        except Exception:
            pass
        return final
    except Exception as exc:
        try:
            _TRANSLATE_LOGGER.info('translation: "%s" -> "%s"', text, text)
            _TRANSLATE_LOGGER.warning('translation failed: %s', exc)
        except Exception:
            pass
        return text
