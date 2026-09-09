"""
Актёрская партитура: эмоции реплик.

Эмоция влияет сразу на три уровня:
  1. Подача TTS — темп, высота, экспрессия (SSML style/degree там, где движок
     это поддерживает).
  2. Тело голоса — микро-дрожание высоты (vibrato/tremor), надрыв, придыхание.
  3. Тракт — сильнее ли пережат компрессор, ближе ли рот к микрофону,
     появляется ли перегруз от крика.

Названия эмоций совпадают с тегами из XML-сценариев игры (emotions="...") и
дополнены собственными для реплик рации.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Emotion:
    key: str
    rate: float = 1.0            # множитель темпа
    pitch: float = 0.0           # полутоны
    volume_db: float = 0.0       # подача по громкости
    drive_mul: float = 1.0       # доп. перегруз (крик «сажает» микрофон)
    comp_extra: float = 0.0      # доп. компрессия (порог вниз, дБ)
    tremor: float = 0.0          # дрожь голоса 0..1 (слёзы, страх, боль)
    tremor_hz: float = 5.5
    breath: float = 0.0          # придыхание/одышка 0..1
    presence_db: float = 0.0     # доп. разборчивость
    style: str = ""              # стиль для TTS-движков, которые его умеют
    style_degree: float = 1.0


EMOTIONS = {
    # --- нейтральные / служебные
    "neutral":   Emotion("neutral"),
    "calm":      Emotion("calm", rate=0.97, pitch=-0.5, style="calm"),
    "formal":    Emotion("formal", rate=0.99, pitch=-0.5, presence_db=1.0),
    "tired":     Emotion("tired", rate=0.93, pitch=-1.0, volume_db=-1.5, breath=0.25),

    # --- напряжение и действие
    "urgent":    Emotion("urgent", rate=1.10, pitch=1.0, volume_db=1.5,
                         comp_extra=2.0, presence_db=1.5, style="chat"),
    "tense":     Emotion("tense", rate=1.05, pitch=0.5, comp_extra=1.5, breath=0.15),
    "shout":     Emotion("shout", rate=1.16, pitch=3.0, volume_db=4.0, drive_mul=1.55,
                         comp_extra=5.0, presence_db=3.0, breath=0.3, style="angry",
                         style_degree=1.6),
    "combat":    Emotion("combat", rate=1.20, pitch=3.5, volume_db=4.5, drive_mul=1.8,
                         comp_extra=6.0, presence_db=3.5, breath=0.45, tremor=0.12,
                         style="angry", style_degree=2.0),
    "angry":     Emotion("angry", rate=1.08, pitch=1.5, volume_db=2.5, drive_mul=1.35,
                         comp_extra=3.0, style="angry", style_degree=1.4),
    "panic":     Emotion("panic", rate=1.22, pitch=3.5, volume_db=3.5, drive_mul=1.4,
                         comp_extra=4.5, tremor=0.35, tremor_hz=6.5, breath=0.5,
                         presence_db=2.5, style="fearful", style_degree=2.0),
    "fear":      Emotion("fear", rate=1.08, pitch=2.0, volume_db=0.5, tremor=0.3,
                         tremor_hz=6.0, breath=0.4, style="fearful", style_degree=1.5),

    # --- беда, боль, слёзы
    "crying":    Emotion("crying", rate=0.94, pitch=2.0, volume_db=-0.5, tremor=0.45,
                         tremor_hz=4.5, breath=0.55, style="sad", style_degree=2.0),
    "pain":      Emotion("pain", rate=0.90, pitch=1.5, volume_db=0.5, tremor=0.4,
                         tremor_hz=5.0, breath=0.6, drive_mul=1.15, style="sad",
                         style_degree=1.6),
    "dying":     Emotion("dying", rate=0.78, pitch=-1.0, volume_db=-3.0, tremor=0.3,
                         tremor_hz=3.5, breath=0.85, style="sad", style_degree=2.0),
    "sad":       Emotion("sad", rate=0.93, pitch=-0.5, volume_db=-1.0, breath=0.25,
                         style="sad", style_degree=1.3),
    "desperate": Emotion("desperate", rate=1.05, pitch=2.5, volume_db=1.5, tremor=0.35,
                         breath=0.45, style="sad", style_degree=2.0),

    # --- прочие состояния звонящих
    "drunk":     Emotion("drunk", rate=0.82, pitch=-2.0, volume_db=0.5, breath=0.35,
                         tremor=0.18, tremor_hz=3.0, drive_mul=1.1),
    "whisper":   Emotion("whisper", rate=0.92, pitch=-1.0, volume_db=-6.0, breath=0.9,
                         presence_db=2.0, style="whispering", style_degree=2.0),
    "confused":  Emotion("confused", rate=0.96, pitch=0.5, breath=0.2),
    "nervous":   Emotion("nervous", rate=1.12, pitch=1.5, tremor=0.2, breath=0.3),
    "child":     Emotion("child", rate=1.05, pitch=5.0, volume_db=0.0, breath=0.2),
    "elderly":   Emotion("elderly", rate=0.86, pitch=-1.0, tremor=0.22, tremor_hz=4.0,
                         breath=0.35),
    "relieved":  Emotion("relieved", rate=0.97, pitch=0.5, breath=0.3),
    "hostile":   Emotion("hostile", rate=1.05, pitch=0.5, volume_db=2.0, drive_mul=1.3,
                         style="angry", style_degree=1.5),
    "sarcastic": Emotion("sarcastic", rate=0.98, pitch=0.5, style="cheerful",
                         style_degree=0.6),
}


# Теги emotions="..." из XML игры → наши эмоции.
XML_EMOTION_MAP = [
    (("scream", "shout", "yell"), "shout"),
    (("panic", "hysteric", "terrified", "terror"), "panic"),
    (("afraid", "scared", "fright", "fear"), "fear"),
    (("cry", "sob", "weep", "tears"), "crying"),
    (("pain", "hurt", "wound", "injur", "moan"), "pain"),
    (("dying", "dies", "faint", "weak", "agony"), "dying"),
    (("angry", "anger", "furious", "mad", "irritat", "aggressive", "rage"), "angry"),
    (("hostile", "rude", "insult"), "hostile"),
    (("drunk", "slur", "intoxicat", "dazed", "high"), "drunk"),
    (("whisper", "quiet", "silent", "hush"), "whisper"),
    (("nervous", "anxious", "worried", "hurried", "stress"), "nervous"),
    (("confus", "unsure", "puzzl", "lost"), "confused"),
    (("sad", "depress", "grief"), "sad"),
    (("desperate", "helpless", "plead", "beg"), "desperate"),
    (("child", "kid", "boy", "girl"), "child"),
    (("old", "elder", "senior", "grandma", "grandpa"), "elderly"),
    (("calm", "relax"), "calm"),
    (("tired", "sleepy", "exhaust"), "tired"),
    (("relief", "relieved", "thank"), "relieved"),
    (("sarcas", "mock", "irony"), "sarcastic"),
    (("urgent", "hurry", "fast"), "urgent"),
]


def from_xml_tag(raw: str) -> str:
    """Определить эмоцию по атрибуту emotions="..." из XML сценария вызова."""
    if not raw:
        return "neutral"
    text = raw.lower()
    for needles, emotion in XML_EMOTION_MAP:
        for n in needles:
            if n in text:
                return emotion
    return "neutral"


def from_text(text: str, default: str = "neutral") -> str:
    """
    Эвристика по самой реплике: восклицания, капс, многоточия, лексика.
    Работает как страховка, когда в XML эмоция не проставлена.
    """
    if not text:
        return default
    t = text.strip()
    low = t.lower()

    bang = t.count("!")
    letters = [c for c in t if c.isalpha()]
    caps_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0.0

    hot_words = ("помогите", "спасите", "быстрее", "срочно", "горим", "горит",
                 "стреляют", "убива", "тону", "умира", "кровь", "задыха")
    cry_words = ("не могу", "боже", "господи", "пожалуйста", "он не дышит",
                 "она не дышит", "мой сын", "моя дочь", "ребёнок", "ребенок")
    pain_words = ("больно", "нога", "рука сломан", "перелом", "ожог", "истека")

    if caps_ratio > 0.6 and len(letters) > 6:
        return "shout"
    if bang >= 2 and any(w in low for w in hot_words):
        return "panic"
    if bang >= 2:
        return "urgent"
    if any(w in low for w in pain_words):
        return "pain"
    if any(w in low for w in cry_words):
        return "crying"
    if any(w in low for w in hot_words):
        return "urgent"
    if t.count("...") >= 2:
        return "confused"
    if t.endswith("?"):
        return default
    return default


def get(name: str) -> Emotion:
    return EMOTIONS.get(name, EMOTIONS["neutral"])
