"""
MORSE-core — API ядра для трёх продуктов (форма DW, MORSE-переводчик, обучающий
конструктор). Этап D0: скелет сборки, часть эндпоинтов — рабочие заглушки.

Разделение труда (раздел 0 плана): нейросеть — только на входе живой язык
(/translate, /asr). Сторона МОРЗЕ (/check, /to_umr, /from_umr) — только
правила, без нейросети; на этапе D0 разборщик/генератор/проверяльщик ещё не
готовы (см. планы A и B), поэтому эти три эндпоинта пока возвращают
501 Not Implemented с понятным сообщением, а не выдуманный результат.
"""

import logging
import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas import (
    AsrResponse,
    CheckRequest,
    CheckResponse,
    FromUmrRequest,
    FromUmrResponse,
    IconsRequest,
    IconsResponse,
    ToUmrRequest,
    ToUmrResponse,
    TranslateRequest,
    TranslateResponse,
    TtsRequest,
)

logger = logging.getLogger("morse-core")

MODEL_SERVER_URL = os.environ.get("MODEL_SERVER_URL", "http://model-server:11434/v1")
MODEL_SERVER_MODEL = os.environ.get("MODEL_SERVER_MODEL", "qwen3:4b")
ICONS_DIR = Path(os.environ.get("ICONS_DIR", "/data/icons"))

app = FastAPI(
    title="MORSE-core",
    version="0.0.1-d0",
    description="Ядро: переводчик, проверяльщик, разборщик/генератор UMR, картинки, речь.",
)

NOT_READY = (
    "Этот эндпоинт — заглушка этапа D0. Разборщик/генератор/проверяльщик "
    "МОРЗЕ зависят от замороженной грамматики (план A) и таблицы соответствия "
    "МОРЗЕ↔UMR (план B, этап B1-B3); до их готовности здесь честная ошибка, "
    "а не придуманный ответ."
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "stage": "D0"}


@app.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest) -> TranslateResponse:
    """
    Живой язык → МОРЗЕ. На D0 — прямой вызов модели без грамматики в
    системной подсказке (грамматика v1.0 ещё не заморожена, план A1) и без
    проверяльщика в контуре (план B2 ещё не готов). Это временный режим
    для замера скорости и проверки связки сервисов, не для оценки точности.
    """
    prompt = (
        "Переведи следующий текст на упрощённый язык MORSE "
        "(короткие фразы, порядок слов подлежащее-сказуемое-дополнение, "
        "без лишних грамматических форм). Пока нет точной грамматики — "
        "переводи как можно ближе к буквальному смыслу.\n\n"
        f"Текст: {req.text}"
    )
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{MODEL_SERVER_URL}/chat/completions",
                json={
                    "model": MODEL_SERVER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Модель-сервер недоступен: {exc}") from exc

    data = resp.json()
    morse_text = data["choices"][0]["message"]["content"].strip()
    return TranslateResponse(morse_text=morse_text, checker_passed=False, checker_errors=["проверяльщик ещё не подключён (D0)"])


@app.post("/check", response_model=CheckResponse)
async def check(req: CheckRequest) -> CheckResponse:
    raise HTTPException(status_code=501, detail=NOT_READY)


@app.post("/to_umr", response_model=ToUmrResponse)
async def to_umr(req: ToUmrRequest) -> ToUmrResponse:
    raise HTTPException(status_code=501, detail=NOT_READY)


@app.post("/from_umr", response_model=FromUmrResponse)
async def from_umr(req: FromUmrRequest) -> FromUmrResponse:
    raise HTTPException(status_code=501, detail=NOT_READY)


@app.post("/icons", response_model=IconsResponse)
async def icons(req: IconsRequest) -> IconsResponse:
    """
    Словарь картинок по номерам концептов. На D0 просто отдаёт то, что нашлось
    в локальном реестре (если он примонтирован); реестр берётся из CONCEPT_LEDGER
    (см. HANDOFF, раздел 3 «Картинки»), сюда он пока не скопирован.
    """
    if not ICONS_DIR.exists():
        return IconsResponse(icons=[])
    found = []
    for cid in req.concept_ids:
        match = list(ICONS_DIR.glob(f"**/{cid}*"))
        if match:
            found.append({"concept_id": cid, "word": {}, "image_url": f"/icons/{match[0].name}"})
    return IconsResponse(icons=found)


@app.post("/tts")
async def tts(req: TtsRequest):
    """
    Синтез речи. RU/EN — Piper (см. requirements.txt); UZ/TJ ещё не подключены
    (голоса — отдельная подзадача, раздел 4 плана). Заглушка на D0: если
    голосовая модель Piper не установлена в контейнере, вернуть понятную ошибку
    вместо тишины.
    """
    voice_path = Path(f"/data/voices/{req.lang}.onnx")
    if not voice_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Голос Piper для языка '{req.lang}' не установлен (ожидается {voice_path}).",
        )
    # Реальный вызов piper — следующий шаг (после первого прогона D0).
    raise HTTPException(status_code=501, detail="Синтез речи будет подключён на следующем шаге D0.")


@app.post("/asr", response_model=AsrResponse)
async def asr(file: UploadFile = File(...)) -> AsrResponse:
    """
    Распознавание речи через faster-whisper (large-v3-turbo). Загружает модель
    лениво при первом вызове (не на старте контейнера), чтобы /health не ждал
    загрузки модели.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"faster-whisper не установлен: {exc}") from exc

    global _whisper_model
    if "_whisper_model" not in globals():
        _whisper_model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")

    tmp_path = Path(f"/tmp/{file.filename}")
    with tmp_path.open("wb") as f:
        f.write(await file.read())

    start = time.time()
    segments, info = _whisper_model.transcribe(str(tmp_path))
    text = " ".join(seg.text for seg in segments)
    logger.info("ASR за %.2fs, язык=%s", time.time() - start, info.language)
    return AsrResponse(text=text.strip(), lang_detected=info.language)


@app.get("/icons/{filename}")
async def get_icon(filename: str):
    path = ICONS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Картинка не найдена")
    return FileResponse(path)
