from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
import structlog

logger = structlog.get_logger()

LANG_MAP = {
    "en": "en",
    "ms": "bm",
    "id": "bm",  # Indonesian is close to Malay
    "zh-cn": "zh",
    "zh-tw": "zh",
    "zh": "zh",
}


def detect_language(text: str) -> str:
    try:
        detected = detect(text)
        return LANG_MAP.get(detected, "en")
    except LangDetectException:
        return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    if source_lang == "en":
        return text

    try:
        source_code = "ms" if source_lang == "bm" else "zh-CN" if source_lang == "zh" else source_lang
        translated = GoogleTranslator(source=source_code, target="en").translate(text)
        return translated or text
    except Exception as e:
        logger.warning("translation_failed", source=source_lang, error=str(e))
        return text


def translate_from_english(text: str, target_lang: str) -> str:
    if target_lang == "en":
        return text

    try:
        target_code = "ms" if target_lang == "bm" else "zh-CN" if target_lang == "zh" else target_lang
        translated = GoogleTranslator(source="en", target=target_code).translate(text)
        return translated or text
    except Exception as e:
        logger.warning("translation_failed", target=target_lang, error=str(e))
        return text
