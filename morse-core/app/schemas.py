"""
Модели запросов/ответов для МОРЗЕ-ядра (черновик, этап D0).

Окончательный контракт API (/translate, /check, /to_umr, /from_umr, /icons,
/tts, /asr) утверждается в плане C2 (MORSE_CORE_API_v1.md, OpenAPI) —
эти схемы будут приведены в соответствие, когда контракт зафиксирован.
Пока это рабочие заглушки для этапа D0.
"""

from typing import Literal

from pydantic import BaseModel, Field

Lang = Literal["ru", "en", "uz", "tj"]


class TranslateRequest(BaseModel):
    text: str = Field(..., description="Исходный текст на живом языке")
    source_lang: Lang = "ru"
    target_lang: Literal["morse-ru", "morse-en", "morse-uz", "morse-tj"] = "morse-ru"


class TranslateResponse(BaseModel):
    morse_text: str
    checker_passed: bool
    checker_errors: list[str] = []
    attempts: int = 1


class CheckRequest(BaseModel):
    morse_text: str
    lang: Lang = "ru"


class CheckError(BaseModel):
    position: int
    rule: str
    message: str


class CheckResponse(BaseModel):
    valid: bool
    errors: list[CheckError] = []


class ToUmrRequest(BaseModel):
    morse_text: str
    lang: Lang = "ru"


class ToUmrResponse(BaseModel):
    umr_penman: str
    umr_graph: dict


class FromUmrRequest(BaseModel):
    umr_penman: str
    target_lang: Lang = "ru"


class FromUmrResponse(BaseModel):
    morse_text: str


class IconsRequest(BaseModel):
    concept_ids: list[str]


class IconEntry(BaseModel):
    concept_id: str
    word: dict[Lang, str]
    image_url: str | None = None


class IconsResponse(BaseModel):
    icons: list[IconEntry]


class TtsRequest(BaseModel):
    text: str
    lang: Lang = "ru"


class AsrResponse(BaseModel):
    text: str
    lang_detected: Lang | None = None
