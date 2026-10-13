"""
MORSE-переводчик — интерфейс Gradio (этап D0, прототип).

Текст + микрофон + звук + полоса картинок, как описано в плане D и в
форме C1. На D0 вызывает только /translate ядра (/check, /to_umr,
/from_umr ещё не готовы — см. morse-core); /asr и /tts подключаются,
когда соответствующие эндпоинты перестанут быть заглушками.
"""

import os

import gradio as gr
import httpx

MORSE_CORE_URL = os.environ.get("MORSE_CORE_URL", "http://morse-core:8000")

LANGS = {"Русский": "ru", "English": "en", "Oʻzbek": "uz", "Тоҷикӣ": "tj"}
TARGETS = {
    "МОРЗЕ-русский": "morse-ru",
    "МОРЗЕ-английский": "morse-en",
    "МОРЗЕ-узбекский": "morse-uz",
    "МОРЗЕ-таджикский": "morse-tj",
}


def translate(text: str, source_lang_label: str, target_label: str):
    if not text.strip():
        return "", "Введите текст."
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{MORSE_CORE_URL}/translate",
                json={
                    "text": text,
                    "source_lang": LANGS[source_lang_label],
                    "target_lang": TARGETS[target_label],
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        return "", f"Ядро недоступно: {exc}"

    status = "проверено" if data.get("checker_passed") else "без проверки (D0)"
    return data.get("morse_text", ""), status


def transcribe_audio(audio_path: str | None, source_lang_label: str):
    if not audio_path:
        return ""
    lang_code = LANGS[source_lang_label]
    try:
        with httpx.Client(timeout=120.0) as client, open(audio_path, "rb") as f:
            resp = client.post(
                f"{MORSE_CORE_URL}/asr",
                files={"file": f},
                data={"lang": lang_code},
            )
            if resp.status_code in (501, 503, 500):
                return f"(распознавание речи недоступно: {resp.json().get('detail', resp.text)})"
            resp.raise_for_status()
            return resp.json().get("text", "")
    except httpx.HTTPError as exc:
        return f"Ядро недоступно: {exc}"


def toggle_mic(source_lang_label: str):
    """Узбекский/таджикский — без распознавания речи в MVP (решение
    владельца 13.10.2026, см. MORSE_SPEECH_CHECK_UZ_TJ_D0_20261013.md):
    отключаем микрофон вместо того, чтобы пускать на заведомо нерабочий
    запрос."""
    lang_code = LANGS[source_lang_label]
    if lang_code in ("uz", "tj"):
        return gr.update(
            interactive=False,
            label="Микрофон недоступен для этого языка в MVP (см. HANDOFF)",
        )
    return gr.update(interactive=True, label="Или наговорить (микрофон)")


with gr.Blocks(title="MORSE-переводчик") as demo:
    gr.Markdown("# MORSE-переводчик (прототип, этап D0)")
    gr.Markdown(
        "Бесплатный словарь-переводчик живой язык ↔ МОРЗЕ. "
        "На этом этапе — только перевод без проверяльщика; картинки и речь "
        "подключаются на следующих шагах."
    )

    with gr.Row():
        source_lang = gr.Dropdown(list(LANGS), value="Русский", label="Язык ввода")
        target_lang = gr.Dropdown(list(TARGETS), value="МОРЗЕ-русский", label="Куда переводим")

    with gr.Row():
        with gr.Column():
            text_in = gr.Textbox(lines=4, label="Текст")
            mic_in = gr.Audio(sources=["microphone"], type="filepath", label="Или наговорить (микрофон)")
            btn = gr.Button("Перевести на МОРЗЕ", variant="primary")
        with gr.Column():
            text_out = gr.Textbox(lines=4, label="МОРЗЕ-текст")
            status_out = gr.Textbox(label="Статус проверки")

    icon_strip = gr.Gallery(label="Полоса картинок (подключается на шаге D4)", columns=8, visible=True)

    mic_in.change(transcribe_audio, inputs=[mic_in, source_lang], outputs=text_in)
    source_lang.change(toggle_mic, inputs=source_lang, outputs=mic_in)
    btn.click(translate, inputs=[text_in, source_lang, target_lang], outputs=[text_out, status_out])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
