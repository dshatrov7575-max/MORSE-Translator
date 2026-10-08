"""
Замер скорости Qwen3-4B / Qwen3-8B (GGUF) на LM Studio без видеокарты.

Запуск на машине LM-STUDIO:
    1. lms load qwen/qwen3-4b -y   (или qwen/qwen3-8b)
    2. lms server start
    3. python speed_test_lm_studio.py --model qwen/qwen3-4b --out report_4b.json

Пишет результат в JSON-файл (не в консоль — кириллица в консоли этой машины
искажается, см. HANDOFF, раздел 3).
"""

import argparse
import json
import time
import urllib.request

PROMPT_RU_1KB = (
    "Мастер первой смены сообщил, что насосная станция номер три остановлена "
    "из-за повышенной вибрации на подшипниковом узле главного насоса. Утром "
    "дежурный инженер провёл осмотр и обнаружил следы износа на уплотнении "
    "вала, а также небольшую течь масла из корпуса редуктора. Было принято "
    "решение заменить подшипник и уплотнение, а также проверить центровку "
    "вала относительно электродвигателя. Ремонтная бригада получила наряд-"
    "допуск на работы с отключением электропитания и приступила к разборке "
    "узла. Запасные части — подшипник, уплотнительное кольцо и смазка — были "
    "получены со склада в течение часа. После замены деталей выполнили "
    "контрольный пуск станции на пониженных оборотах и зафиксировали уровень "
    "вибрации в норме. Станцию вернули в рабочий режим к вечеру, отчёт о "
    "простое и выполненных работах направлен старшему мастеру и в службу "
    "главного механика для внесения в журнал технического обслуживания "
    "оборудования и планирования следующего планового осмотра через месяц."
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Например: qwen/qwen3-4b")
    ap.add_argument("--host", default="http://localhost:1234/v1")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    text_bytes = len(PROMPT_RU_1KB.encode("utf-8"))

    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": f"Перескажи кратко своими словами (3-4 предложения):\n\n{PROMPT_RU_1KB}",
            }
        ],
        "temperature": 0.2,
        "max_tokens": 400,
        # Qwen3 поддерживает режим рассуждений ("thinking"), который резко
        # увеличивает число токенов и время генерации, искажая замер
        # скорости перевода. Отключаем явно; сервер, не знающий это поле,
        # просто его проигнорирует.
        "chat_template_kwargs": {"enable_thinking": False},
    }

    req = urllib.request.Request(
        f"{args.host}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - t0

    usage = data.get("usage", {})
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")

    result = {
        "model": args.model,
        "input_bytes_utf8": text_bytes,
        "elapsed_seconds": round(elapsed, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_per_second": round(completion_tokens / elapsed, 2) if completion_tokens else None,
        "seconds_per_1kb_input_equivalent": round(elapsed * 1024 / text_bytes, 2),
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
