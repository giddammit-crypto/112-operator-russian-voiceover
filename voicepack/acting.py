"""
Актёрская адаптация реплик вызовов 112.

Здесь не меняется смысл сценария игры: модуль добавляет только то, что живой
актёр дублирования обычно делает сам — микропаузы, короткие вдохи/выдохи,
заикание на первом слове при страхе, сдержанность оператора. Всё детерминировано
по seed, чтобы одна и та же реплика всегда пересобиралась одинаково.
"""

from __future__ import annotations

import random
import re


_DISTRESS_PREFIXES = {
    "panic": ("Господи... ", "Ах... ", "Пожалуйста... "),
    "fear": ("Тихо... ", "Я... я... ", "Господи... "),
    "crying": ("Пожалуйста... ", "Господи... ", "Я... я... "),
    "desperate": ("Пожалуйста... ", "Господи, ну... ", "Прошу вас... "),
    "pain": ("Ох... ", "Ах... ", "Ух... "),
    "dying": ("Ох... ", "Я... ", "Тише... "),
    "nervous": ("Так... ", "Я... ", "Секунду... "),
    "confused": ("Я... ", "Подождите... ", "Не понимаю... "),
    "drunk": ("Э-э... ", "Слушайте... ", "Ну... "),
}

# Для коротких реплик повтор первого слова звучит естественнее, чем длинный
# префикс: «Я... я не могу дышать», «Он... он упал».
_STUTTER_EMOTIONS = {"panic", "fear", "crying", "desperate", "pain", "dying", "nervous"}

# Операторские кнопки часто содержат сухую UI-формулировку. Оператор должен
# звучать как диспетчер, а не как читатель меню.
_OPERATOR_SOFTENERS = (
    (re.compile(r"^что случилось\??$", re.I), "Что у вас произошло?"),
    (re.compile(r"^что произошло\??$", re.I), "Что у вас произошло?"),
    (re.compile(r"^где вы\??$", re.I), "Назовите адрес, где вы находитесь."),
    (re.compile(r"^ваш адрес\??$", re.I), "Назовите точный адрес."),
    (re.compile(r"^успокойтесь\.?$", re.I), "Постарайтесь говорить медленно. Я вас слушаю."),
)


def _first_word_stutter(text: str) -> str:
    m = re.match(r"^([А-Яа-яЁёA-Za-z]{2,})([\s,!.?—-]+)(.+)$", text.strip())
    if not m:
        return text
    word, sep, rest = m.group(1), m.group(2), m.group(3)
    if len(word) > 12:
        return text
    return f"{word}... {word.lower()}{sep}{rest}"


def perform_call_text(text: str, emotion: str, seed: int, *, is_operator: bool = False) -> str:
    """Вернуть реплику в форме, пригодной для актёрского TTS-дубля."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return t

    if is_operator:
        low = t.strip().rstrip(".")
        for rx, repl in _OPERATOR_SOFTENERS:
            if rx.match(low):
                return repl
        # Убираем чрезмерные эмоции у оператора, но оставляем вопросы и паузы.
        t = re.sub(r"!+", ".", t)
        t = re.sub(r"\.{3,}", "…", t)
        return t

    rng = random.Random(seed)
    out = t

    if emotion in _STUTTER_EMOTIONS and rng.random() < 0.45 and len(out) < 120:
        out = _first_word_stutter(out)

    if emotion in _DISTRESS_PREFIXES:
        # Не добавляем междометие, если оно уже есть в тексте.
        if not re.match(r"^(ах|ох|ух|господи|пожалуйста|прошу|эй|э-э)\b", out, re.I):
            probability = {
                "panic": 0.55,
                "fear": 0.45,
                "crying": 0.60,
                "desperate": 0.65,
                "pain": 0.70,
                "dying": 0.80,
                "nervous": 0.35,
                "confused": 0.30,
                "drunk": 0.40,
            }.get(emotion, 0.0)
            if rng.random() < probability:
                out = rng.choice(_DISTRESS_PREFIXES[emotion]) + out

    # Пунктуация как режиссура дыхания: слишком много восклицаний TTS часто
    # превращает в крик-робот. Оставляем один знак и добавляем паузу.
    out = re.sub(r"!{2,}", "!", out)
    if emotion in {"panic", "fear", "crying", "desperate", "pain", "dying"}:
        out = re.sub(r"([.!?])\s+", r"\1 … ", out, count=1)

    return re.sub(r"\s+", " ", out).strip()
