"""
Кастинг и звуковой тракт персонажей.

Каждый персонаж — это не просто «голос TTS», а полноценная роль:
  * актёрская подача (темп, высота, экспрессия на уровне TTS/SSML);
  * анатомия голоса (varispeed + формантный наклон — чтобы 4 разных бойца
    не звучали как один диктор);
  * личный тракт: тип микрофона, полоса радиостанции, компрессия, сатурация,
    уровень эфирного шума.

Такой подход даёт кинематографичный результат даже на одном TTS-движке:
экипажи различимы на слух, как в дубляже экшен-фильма.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VoiceProfile:
    """Роль: как персонаж говорит и как звучит его канал связи."""

    key: str
    title: str                      # человекочитаемое описание роли
    sex: str                        # "male" / "female"
    tts_voice: str                  # предпочтительный голос TTS
    tts_fallbacks: tuple = ()       # запасные голоса, если основной недоступен

    # --- актёрская подача (базовая, эмоция накладывается сверху)
    rate: float = 1.0               # множитель темпа речи
    pitch_semitones: float = 0.0    # сдвиг высоты на уровне TTS

    # --- анатомия голоса (после синтеза)
    varispeed: float = 1.0          # 0.95 = крупнее/ниже, 1.05 = легче/выше
    formant: float = 0.0            # >0 плотнее, <0 светлее

    # --- эфирный тракт
    band_low: float = 380.0         # нижняя граница полосы радиостанции, Гц
    band_high: float = 3400.0       # верхняя граница, Гц
    band_order: int = 3             # крутизна (order * 12 дБ/окт)
    presence_db: float = 4.5        # подъём разборчивости 2.2-3 кГц
    body_db: float = 0.0            # тело голоса ~200-400 Гц (в рации немного)
    drive: float = 1.5              # сатурация усилителя радиостанции
    sat_kind: str = "tanh"
    comp_threshold: float = -20.0
    comp_ratio: float = 5.0
    hiss_db: float = -42.0          # эфирный шип
    crackle_db: float = -34.0       # треск
    dropout_count: int = 0          # провалы связи
    roger_beep: bool = False        # «роджер-бип» в конце передачи
    mic_distance: float = 0.0       # 0 = вплотную, 1 = микрофон далеко
    target_rms_db: float = -17.0
    tags: tuple = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Экипажи на рации
# ---------------------------------------------------------------------------

RADIO_CAST = {
    # Опытный командир экипажа. Низкий, спокойный, «военная» дикция.
    "Male1": VoiceProfile(
        key="Male1",
        title="Командир экипажа — низкий, собранный, уставная дикция",
        sex="male",
        tts_voice="ru-RU-DmitryNeural",
        tts_fallbacks=("ru-RU-DmitryNeural",),
        rate=0.98,
        pitch_semitones=-1.5,
        varispeed=0.965,
        formant=0.55,
        band_low=330.0, band_high=3300.0, band_order=3,
        presence_db=4.0, body_db=2.0,
        drive=1.45, sat_kind="tanh",
        comp_threshold=-21.0, comp_ratio=4.5,
        hiss_db=-44.0, crackle_db=-36.0,
        dropout_count=1,
        roger_beep=True,
        target_rms_db=-17.0,
        tags=("calm", "authority"),
    ),
    # Штурмовик. Быстро, зло, на адреналине, микрофон «съеден».
    "Male2": VoiceProfile(
        key="Male2",
        title="Боец группы захвата — быстрый, на адреналине, кричит в тангенту",
        sex="male",
        tts_voice="ru-RU-DmitryNeural",
        rate=1.13,
        pitch_semitones=1.5,
        varispeed=1.035,
        formant=-0.15,
        band_low=420.0, band_high=3200.0, band_order=4,
        presence_db=6.5, body_db=-1.0,
        drive=2.6, sat_kind="atan",
        comp_threshold=-25.0, comp_ratio=8.0,
        hiss_db=-37.0, crackle_db=-28.0,
        dropout_count=2,
        roger_beep=False,
        mic_distance=0.0,
        target_rms_db=-15.5,
        tags=("hot", "adrenaline"),
    ),
    # Старший диспетчер/координатор. Чеканно, ровно, командно.
    "Female1": VoiceProfile(
        key="Female1",
        title="Координатор смены — чеканная командная речь",
        sex="female",
        tts_voice="ru-RU-SvetlanaNeural",
        rate=1.02,
        pitch_semitones=-0.5,
        varispeed=0.985,
        formant=0.15,
        band_low=360.0, band_high=3500.0, band_order=3,
        presence_db=4.5, body_db=1.0,
        drive=1.4, sat_kind="tanh",
        comp_threshold=-20.0, comp_ratio=4.5,
        hiss_db=-45.0, crackle_db=-38.0,
        dropout_count=0,
        roger_beep=True,
        target_rms_db=-17.0,
        tags=("calm", "command"),
    ),
    # Патрульная на передовой. Живые эмоции, надрыв, шум вокруг.
    "Female2": VoiceProfile(
        key="Female2",
        title="Патрульная на передовой — живые эмоции, надрыв",
        sex="female",
        tts_voice="ru-RU-SvetlanaNeural",
        rate=1.11,
        pitch_semitones=1.0,
        varispeed=1.025,
        formant=-0.25,
        band_low=430.0, band_high=3300.0, band_order=4,
        presence_db=6.0, body_db=-0.5,
        drive=2.3, sat_kind="atan",
        comp_threshold=-24.0, comp_ratio=7.0,
        hiss_db=-38.0, crackle_db=-30.0,
        dropout_count=2,
        roger_beep=False,
        target_rms_db=-15.5,
        tags=("hot", "emotional"),
    ),
    # Фоновый эфир дежурной части: тише, глуше, «в соседней комнате».
    "Chatter": VoiceProfile(
        key="Chatter",
        title="Фоновый радиообмен дежурной части",
        sex="male",
        tts_voice="ru-RU-DmitryNeural",
        rate=1.05,
        pitch_semitones=-1.0,
        varispeed=0.99,
        formant=0.3,
        band_low=520.0, band_high=2900.0, band_order=4,
        presence_db=3.0, body_db=-2.0,
        drive=1.9, sat_kind="tanh",
        comp_threshold=-24.0, comp_ratio=6.0,
        hiss_db=-34.0, crackle_db=-30.0,
        dropout_count=2,
        roger_beep=False,
        mic_distance=0.5,
        target_rms_db=-24.0,
        tags=("background",),
    ),
}

# Второй голос каждой роли — чтобы в эфире было слышно разных людей,
# а не одного актёра. Применяется к нечётным дублям одной реплики.
RADIO_ALT_TWEAKS = {
    "Male1": {"varispeed": 0.945, "formant": 0.75, "pitch_semitones": -2.5, "rate": 0.96},
    "Male2": {"varispeed": 1.055, "formant": -0.3, "pitch_semitones": 2.5, "rate": 1.16},
    "Female1": {"varispeed": 1.005, "formant": 0.0, "pitch_semitones": 0.5, "rate": 1.04},
    "Female2": {"varispeed": 1.045, "formant": -0.4, "pitch_semitones": 2.0, "rate": 1.14},
    "Chatter": {"varispeed": 1.02, "formant": -0.2, "pitch_semitones": 1.0, "rate": 1.08},
}


# ---------------------------------------------------------------------------
# Звонки 112: оператор и звонящие
# ---------------------------------------------------------------------------

OPERATOR_PROFILE = VoiceProfile(
    key="Operator",
    title="Оператор 112 — спокойный профессионал в гарнитуре",
    sex="male",
    tts_voice="ru-RU-DmitryNeural",
    rate=1.0,
    pitch_semitones=-0.5,
    varispeed=0.985,
    formant=0.3,
    # Гарнитура диспетчера — широкая полоса, это «наша» сторона линии
    band_low=110.0, band_high=8000.0, band_order=2,
    presence_db=2.5, body_db=1.5,
    drive=1.15, sat_kind="tanh",
    comp_threshold=-18.0, comp_ratio=3.5,
    hiss_db=-58.0, crackle_db=-70.0,
    dropout_count=0,
    roger_beep=False,
    target_rms_db=-17.0,
    tags=("studio",),
)

OPERATOR_FEMALE_PROFILE = VoiceProfile(
    key="OperatorFemale",
    title="Оператор 112 (женский голос) — спокойный профессионал",
    sex="female",
    tts_voice="ru-RU-SvetlanaNeural",
    rate=1.0,
    pitch_semitones=-0.5,
    varispeed=0.995,
    formant=0.2,
    band_low=120.0, band_high=8000.0, band_order=2,
    presence_db=2.5, body_db=1.0,
    drive=1.15, sat_kind="tanh",
    comp_threshold=-18.0, comp_ratio=3.5,
    hiss_db=-58.0, crackle_db=-70.0,
    target_rms_db=-17.0,
    tags=("studio",),
)

# Звонящие: пул «актёров массовки», чтобы разные вызовы звучали разными людьми.
CALLER_POOL_MALE = [
    VoiceProfile(key="CallerM1", title="Мужчина, 30-40 лет", sex="male",
                 tts_voice="ru-RU-DmitryNeural",
                 varispeed=1.0, formant=0.0, pitch_semitones=0.0, rate=1.0),
    VoiceProfile(key="CallerM2", title="Мужчина постарше, ниже голос", sex="male",
                 tts_voice="ru-RU-DmitryNeural",
                 varispeed=0.955, formant=0.6, pitch_semitones=-2.0, rate=0.96),
    VoiceProfile(key="CallerM3", title="Молодой парень", sex="male",
                 tts_voice="ru-RU-DmitryNeural",
                 varispeed=1.05, formant=-0.35, pitch_semitones=2.0, rate=1.06),
    VoiceProfile(key="CallerM4", title="Мужчина с хрипотцой", sex="male",
                 tts_voice="ru-RU-DmitryNeural",
                 varispeed=0.975, formant=0.35, pitch_semitones=-1.0, rate=0.99,
                 drive=1.9),
]

CALLER_POOL_FEMALE = [
    VoiceProfile(key="CallerF1", title="Женщина, 30-40 лет", sex="female",
                 tts_voice="ru-RU-SvetlanaNeural",
                 varispeed=1.0, formant=0.0, pitch_semitones=0.0, rate=1.0),
    VoiceProfile(key="CallerF2", title="Женщина постарше", sex="female",
                 tts_voice="ru-RU-SvetlanaNeural",
                 varispeed=0.96, formant=0.5, pitch_semitones=-1.5, rate=0.95),
    VoiceProfile(key="CallerF3", title="Девушка", sex="female",
                 tts_voice="ru-RU-SvetlanaNeural",
                 varispeed=1.055, formant=-0.4, pitch_semitones=1.5, rate=1.05),
    VoiceProfile(key="CallerF4", title="Женщина с низким тембром", sex="female",
                 tts_voice="ru-RU-SvetlanaNeural",
                 varispeed=0.985, formant=0.3, pitch_semitones=-0.5, rate=0.98),
]

# Телефонная линия для всех звонящих (узкая полоса GSM/АТС).
PHONE_LINE = dict(
    band_low=330.0, band_high=3400.0, band_order=4,
    presence_db=4.0, body_db=-1.5,
    drive=1.6, sat_kind="atan",
    comp_threshold=-20.0, comp_ratio=5.0,
    hiss_db=-46.0, crackle_db=-44.0,
    dropout_count=1,
)


def caller_profile(sex: str, index: int, mobile: bool = True) -> VoiceProfile:
    """Подобрать звонящего из пула детерминированно по индексу вызова."""
    pool = CALLER_POOL_FEMALE if sex.upper().startswith("F") else CALLER_POOL_MALE
    base = pool[index % len(pool)]
    p = VoiceProfile(**{**base.__dict__})
    for k, v in PHONE_LINE.items():
        setattr(p, k, v)
    if not mobile:
        # Стационарный телефон: уже полоса, меньше цифровых артефактов
        p.band_low = 300.0
        p.band_high = 3000.0
        p.dropout_count = 0
        p.hiss_db = -50.0
    p.target_rms_db = -17.0
    return p


def variant(profile: VoiceProfile, **tweaks) -> VoiceProfile:
    """Копия профиля с изменёнными полями."""
    data = dict(profile.__dict__)
    data.update(tweaks)
    return VoiceProfile(**data)


def alt_of(key: str) -> VoiceProfile:
    """Второй актёр той же роли (для чередования дублей)."""
    base = RADIO_CAST[key]
    return variant(base, **RADIO_ALT_TWEAKS.get(key, {}))
