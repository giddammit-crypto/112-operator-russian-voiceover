"""
Сборка озвучки экстренных вызовов 112.

Источники правды (из установленной игры):
  * StreamingAssets/Languages/ru-RU.txt — официальный русский текст реплик;
  * StreamingAssets/Calls/**.xml и Calls_911/**.xml — структура диалогов,
    пол звонящего, эмоции, кто говорит (оператор или абонент).

Выход: <out>/RussianCalls/<call_id>/<option_id>.wav + manifest.
Загрузчик мода (RussianRadioManager.GetOrLoadCallClip) ждёт ровно такую схему.

Ключевые отличия от прежней версии:
  * текст нормализуется для речи: числа, сокращения, «112» → «сто двенадцать»,
    убираются экранные теги, ремарки в скобках и служебная разметка;
  * эмоция берётся из XML, а если её нет — определяется по самой реплике;
  * звонящий выбирается из пула «актёров», так что разные вызовы звучат
    разными людьми, а внутри одного вызова голос постоянен;
  * добавляется акустика места события (улица/помещение/машина/толпа);
  * реплики без текста дают корректную паузу или гудки отбоя.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET

from . import dsp
from .acting import perform_call_text
from .casting import OPERATOR_PROFILE, OPERATOR_FEMALE_PROFILE, caller_profile
from .emotions import from_text, from_xml_tag, get as get_emotion
from .parallel import default_jobs, get_backend, run_tasks
from .render import render_hangup, render_line, render_silence_clip
from .text_norm import normalize_for_speech, split_screen_tag


DIALOG_KEY_RE = re.compile(r'"(incident\.[^"\\:]+\.dialog\.[^"\\:]+)"\s*:\s*"((?:[^"\\]|\\.)*)"')


# ---------------------------------------------------------------------------
# Загрузка исходников игры
# ---------------------------------------------------------------------------

def load_localization(lang_path: str) -> dict[str, str]:
    """Прочитать ru-RU.txt и вернуть {ключ диалога: текст}."""
    texts: dict[str, str] = {}
    with open(lang_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = DIALOG_KEY_RE.search(line)
            if not m:
                continue
            key, raw = m.group(1), m.group(2)
            value = (raw.replace('\\"', '"')
                        .replace("\\n", " ")
                        .replace("\\r", " ")
                        .replace("\\t", " ")
                        .replace("\\\\", "\\"))
            texts[key] = value.strip()
    return texts


def _iter_call_xml(streaming_assets: str):
    for sub in ("Calls", "Calls_911", "Calls_112"):
        d = os.path.join(streaming_assets, sub)
        if os.path.isdir(d):
            yield from glob.glob(os.path.join(d, "**", "*.xml"), recursive=True)


AMBIENCE_HINTS = (
    (("crash", "car", "road", "traffic", "accident", "hitrun", "dtp"), "car"),
    (("street", "outdoor", "park", "robber", "fight", "shoot"), "street"),
    (("fire", "burn", "smoke"), "street"),
    (("crowd", "concert", "stadium", "mall", "riot", "party"), "crowd"),
    (("home", "flat", "apart", "house", "indoor", "kitchen", "bath"), "indoor"),
)


def _ambience_for(call_id: str, text: str = "") -> str:
    """Прикинуть акустику места: сначала по id вызова, затем по самой реплике."""
    low = f"{call_id} {text}".lower()
    ru_hints = (
        (("авар", "дтп", "машин", "дорог", "трасс", "водител", "салон"), "car"),
        (("улиц", "двор", "парк", "подъезд", "стреля", "дерут", "граб"), "street"),
        (("пожар", "горит", "дым", "задыха", "огонь"), "street"),
        (("толп", "магазин", "торгов", "концерт", "стадион", "бар", "клуб"), "crowd"),
        (("квартир", "дом", "кухн", "ванн", "комнат", "сосед"), "indoor"),
    )
    for needles, kind in ru_hints:
        if any(n in low for n in needles):
            return kind
    for needles, kind in AMBIENCE_HINTS:
        if any(n in low for n in needles):
            return kind
    return "indoor"


def _stable_seed(*parts: str) -> int:
    data = "\0".join(str(p) for p in parts).encode("utf-8", "ignore")
    return int.from_bytes(hashlib.sha1(data).digest()[:4], "big")


def _detect_sex(attrs_text: str, default: str = "MALE") -> str:
    up = attrs_text.upper()
    if re.search(r"\b(FEMALE|WOMAN|GIRL|SEX\s*=\s*FEMALE|GENDER\s*=\s*F)\b", up):
        return "FEMALE"
    if re.search(r"\b(MALE|MAN|BOY|SEX\s*=\s*MALE|GENDER\s*=\s*M)\b", up):
        return "MALE"
    return default


def _is_operator_option(opt: ET.Element) -> bool:
    """XML разных версий игры по-разному называет говорящего."""
    attrs = {str(k).lower(): str(v).lower() for k, v in opt.attrib.items()}
    joined = " ".join(f"{k}={v}" for k, v in attrs.items())

    for key in ("operator", "dispatcher", "isoperator", "is_operator"):
        if attrs.get(key) in ("true", "1", "yes", "operator", "dispatcher"):
            return True
    speaker = " ".join(attrs.get(k, "") for k in ("speaker", "from", "who", "character", "actor", "role", "side", "person"))
    if any(w in speaker for w in ("operator", "dispatcher", "dyspozytor", "112")):
        return True
    if any(w in speaker for w in ("caller", "victim", "witness", "suspect", "civilian")):
        return False
    if any(w in joined for w in ("caller", "victim", "witness", "suspect", "civilian")):
        return False
    return False


def parse_calls(streaming_assets: str) -> dict:
    """Собрать метаданные всех вызовов: пол абонента, роли и эмоции реплик."""
    calls: dict[str, dict] = {}
    for path in _iter_call_xml(streaming_assets):
        try:
            root = ET.parse(path).getroot()
        except Exception:
            continue

        incident = root.find("incident")
        node = incident if incident is not None else root
        call_id = (node.get("id") or os.path.splitext(os.path.basename(path))[0])

        sex = "MALE"
        for el in root.iter():
            attrs_text = " ".join(f"{k}={v}" for k, v in el.attrib.items())
            new_sex = _detect_sex(attrs_text, sex)
            if new_sex != sex:
                sex = new_sex
                break

        options = {}
        for opt in root.iter("dialogOption"):
            opt_id = opt.get("id")
            if not opt_id:
                continue
            is_operator = _is_operator_option(opt)
            opt_sex = _detect_sex(" ".join(f"{k}={v}" for k, v in opt.attrib.items()), sex)
            options[opt_id] = {
                "is_operator": is_operator,
                "emotions": opt.get("emotions") or opt.get("emotion") or opt.get("mood") or "",
                "sex": opt_sex,
            }

        if options:
            calls[call_id] = {
                "sex": sex,
                "options": options,
                "source": path,
                "ambience": _ambience_for(call_id),
            }
    return calls


# ---------------------------------------------------------------------------
# Сборка
# ---------------------------------------------------------------------------

HANGUP_HINTS = ("hangup", "hang_up", "disconnect", "endcall", "callend")


def _worker(task: dict) -> dict:
    """Синтез одной реплики вызова (выполняется в пуле процессов)."""
    out_path = task["path"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if task["kind"] in ("hangup", "silence"):
        clip = (render_hangup(task["seed"]) if task["kind"] == "hangup"
                else render_silence_clip(1.0))
        dsp.write_wav(out_path, clip)
        return {"call": task["call"], "option": task["option"], "kind": task["kind"],
                "text": "", "emotion": "", "duration": round(dsp.duration(clip), 3),
                "label": f"{task['call']}/{task['option']} — {task['kind']}"}

    tts = get_backend(task["backend"])
    is_op = task["kind"] == "operator"
    profile = (task["operator_profile"] if is_op
               else caller_profile(task["sex"], task["caller_index"]))
    mode = "headset" if is_op else "phone"

    # Интонацию закладываем уже на этапе TTS: эмоция меняет темп, высоту и,
    # для движков с поддержкой стилей, экспрессию. DSP-слой ниже добавит
    # дрожь, дыхание, телефонный тракт и акустику сцены.
    em = get_emotion(task["emotion"])
    raw = tts.synth(task["text"], profile.tts_voice,
                    rate=profile.rate * em.rate,
                    pitch_semitones=profile.pitch_semitones + em.pitch,
                    style=em.style, style_degree=em.style_degree)
    clip = render_line(raw, profile, task["emotion"], task["seed"], mode=mode,
                       ambience=None if is_op else task["ambience"])
    dsp.write_wav(out_path, clip)

    return {
        "call": task["call"], "option": task["option"], "kind": task["kind"],
        "actor": profile.key, "screen_tag": task["screen_tag"],
        "text": task["text"], "emotion": task["emotion"],
        "duration": round(dsp.duration(clip), 3),
        "label": f"{task['call']}/{task['option']} "
                 f"({'оператор' if is_op else profile.key}, {task['emotion']}, "
                 f"{dsp.duration(clip):.2f}с)",
    }


def build_calls(out_root: str, backend_name: str, streaming_assets: str,
                only_calls: list[str] | None = None, limit: int | None = None,
                operator_voice: str = "male", overwrite: bool = True,
                jobs: int | None = None, progress=print) -> dict:
    lang_path = os.path.join(streaming_assets, "Languages", "ru-RU.txt")
    if not os.path.isfile(lang_path):
        raise FileNotFoundError(
            f"Не найден файл русской локализации: {lang_path}\n"
            "Укажите корректный путь к StreamingAssets установленной игры."
        )

    texts = load_localization(lang_path)
    calls = parse_calls(streaming_assets)
    progress(f"[Звонки] Локализация: {len(texts)} реплик; сценариев: {len(calls)}")

    op_profile = OPERATOR_PROFILE if operator_voice == "male" else OPERATOR_FEMALE_PROFILE
    calls_root = os.path.join(out_root, "RussianCalls")
    jobs = jobs or default_jobs()

    tasks: list[dict] = []
    for ci, (call_id, meta) in enumerate(sorted(calls.items())):
        if only_calls and call_id not in only_calls:
            continue
        for opt_id, om in meta["options"].items():
            key = f"incident.{call_id}.dialog.{opt_id}"
            if key not in texts:
                continue

            out_path = os.path.join(calls_root, call_id, f"{opt_id}.wav")
            if not overwrite and os.path.exists(out_path):
                continue

            is_op = om["is_operator"]
            screen_tag, spoken = split_screen_tag(texts[key])
            spoken = normalize_for_speech(spoken)
            seed = _stable_seed(call_id, opt_id)

            if not spoken or not re.search(r"[A-Za-zА-Яа-яЁё0-9]", spoken):
                kind = ("hangup" if any(h in opt_id.lower() for h in HANGUP_HINTS)
                        else "silence")
                tasks.append({"kind": kind, "call": call_id, "option": opt_id,
                              "path": out_path, "seed": seed,
                              "backend": backend_name})
                continue

            emotion = "calm" if is_op else from_xml_tag(om.get("emotions", ""))
            if not is_op and emotion == "neutral":
                emotion = from_text(spoken)
            spoken = perform_call_text(spoken, emotion, seed, is_operator=is_op)
            ambience = _ambience_for(call_id, spoken) if not is_op else meta["ambience"]

            tasks.append({
                "kind": "operator" if is_op else "caller",
                "call": call_id, "option": opt_id, "path": out_path,
                "text": spoken, "screen_tag": screen_tag, "emotion": emotion,
                "sex": om.get("sex", meta["sex"]), "caller_index": ci,
                "ambience": ambience, "operator_profile": op_profile,
                "seed": seed, "backend": backend_name,
            })

    if limit:
        tasks = tasks[:limit]

    progress(f"[Звонки] К синтезу: {len(tasks)} реплик, потоков: {jobs}")
    t0 = time.time()
    results = [r for r in run_tasks(_worker, tasks, jobs, progress) if r]
    for r in results:
        r.pop("label", None)

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "backend": backend_name,
        "sample_rate": dsp.SR,
        "operator_voice": operator_voice,
        "count": len(results),
        "elapsed_sec": round(time.time() - t0, 1),
        "entries": results,
    }
