"""
Рендер реплики: TTS → актёрская обработка → эфирный тракт → готовый WAV.

Цепочка обработки одной реплики рации:
    TTS
      → обрезка «воздуха», де-эссер, гейт
      → тремор/надрыв, придыхание (эмоция)
      → varispeed + формантный наклон (анатомия персонажа)
      → эквализация «горловины» радиостанции (крутая полоса + presence)
      → компрессия АРУ радиостанции → сатурация усилителя
      → μ-law/bitcrush артефакты цифровой связи → дропауты
      → монтаж: PTT-клик + речь + эфирный шип/треск + squelch-хвост + roger-beep
      → нормализация по RMS + лимитер (без клиппинга)

Для звонков 112 тракт другой: телефонная линия, фон места события,
без PTT-кликов, оператор — чистая студийная гарнитура.
"""

from __future__ import annotations

import math
import random

from . import dsp, fx
from .casting import VoiceProfile
from .dsp import SR, Signal
from .emotions import Emotion, get as get_emotion


# ---------------------------------------------------------------------------
# Актёрские микро-детали
# ---------------------------------------------------------------------------

def apply_tremor(sig: Signal, amount: float, rate_hz: float, rng: random.Random) -> Signal:
    """Дрожь голоса: слёзы, страх, боль, холод. Амплитудно-частотное микроколебание."""
    if amount <= 0.01 or not len(sig):
        return sig
    out = dsp.new_signal(len(sig))
    drift = rng.uniform(0, 2 * math.pi)
    for i, s in enumerate(sig):
        t = i / SR
        wob = 1.0 + amount * 0.35 * math.sin(2 * math.pi * rate_hz * t + drift)
        wob += amount * 0.12 * math.sin(2 * math.pi * (rate_hz * 2.7) * t)
        out[i] = s * wob
    # лёгкая нестабильность высоты — «голос ломается»
    if amount > 0.25:
        out = _pitch_wobble(out, amount * 0.012, rate_hz * 0.6, rng)
    return out


def _pitch_wobble(sig: Signal, depth: float, hz: float, rng: random.Random) -> Signal:
    n = len(sig)
    out = dsp.new_signal(n)
    pos = 0.0
    ph = rng.uniform(0, 2 * math.pi)
    for i in range(n):
        speed = 1.0 + depth * math.sin(2 * math.pi * hz * i / SR + ph)
        i0 = int(pos)
        if i0 >= n - 1:
            out[i] = sig[n - 1]
        else:
            frac = pos - i0
            out[i] = sig[i0] * (1 - frac) + sig[i0 + 1] * frac
        pos += speed
        if pos >= n - 1:
            pos = n - 1
    return out


def add_breath(sig: Signal, amount: float, rng: random.Random) -> Signal:
    """Одышка/придыхание: шумовая составляющая, привязанная к огибающей речи."""
    if amount <= 0.01 or not len(sig):
        return sig
    env = dsp.envelope(sig, 12.0, 90.0)
    mx = max(env, default=0.0) or 1.0
    noise = dsp.white_noise(len(sig), rng)
    noise = dsp.chain(noise, dsp.bandpass(2400.0, 0.5), dsp.highpass(900.0, 0.7))
    out = dsp.new_signal(len(sig))
    level = amount * 0.16
    for i, s in enumerate(sig):
        out[i] = s + noise[i] * (env[i] / mx) * level
    return out


def add_breath_pauses(sig: Signal, amount: float, rng: random.Random) -> Signal:
    """Вдохи перед фразой и в паузах — очень сильно оживляет панику и боль."""
    if amount < 0.35 or not len(sig):
        return sig
    n_breath = int(SR * rng.uniform(0.16, 0.26))
    breath = dsp.white_noise(n_breath, rng)
    breath = dsp.chain(breath, dsp.bandpass(1300.0, 0.45), dsp.lowpass(3000.0, 0.7))
    for i in range(n_breath):
        t = i / n_breath
        breath[i] *= math.sin(math.pi * t) ** 1.4 * 0.10 * amount
    return dsp.concat(breath, dsp.silence(0.03), sig)


# ---------------------------------------------------------------------------
# Эфирный тракт
# ---------------------------------------------------------------------------

def radio_channel(sig: Signal, profile: VoiceProfile, emotion: Emotion,
                  rng: random.Random) -> Signal:
    """Полоса, АРУ, перегруз и цифровые артефакты конкретной радиостанции."""
    out = sig

    # 1. «Горловина» радиостанции: крутой полосовой фильтр
    out = dsp.steep_bandpass(out, profile.band_low, profile.band_high, profile.band_order)

    # 2. Характер: presence для разборчивости, тело — по вкусу роли
    out = dsp.chain(
        out,
        dsp.peaking(2400.0, 1.1, profile.presence_db + emotion.presence_db),
        dsp.peaking(1000.0, 0.9, 1.5),
        dsp.peaking(420.0, 0.8, profile.body_db),
        dsp.peaking(3100.0, 2.0, 2.0),
    )

    # 3. Микрофон дальше от рта — меньше НЧ, больше комнаты
    if profile.mic_distance > 0.01:
        out = dsp.chain(out,
                        dsp.highpass(500.0 + 300.0 * profile.mic_distance, 0.7),
                        dsp.peaking(1800.0, 1.0, -2.0 * profile.mic_distance))

    # 4. АРУ радиостанции — жёстко «клеит» динамику
    out = dsp.compressor(out,
                         threshold_db=profile.comp_threshold - emotion.comp_extra,
                         ratio=profile.comp_ratio + emotion.comp_extra * 0.4,
                         attack_ms=4.0, release_ms=70.0, knee_db=5.0)

    # 5. Перегруз усилителя (крик «сажает» передатчик)
    out = dsp.saturate(out, drive=profile.drive * emotion.drive_mul,
                       kind=profile.sat_kind, mix_=0.9)

    # 6. Артефакты цифрового кодека
    out = dsp.mulaw(out, mu=255.0, mix_=0.55)
    out = dsp.bitcrush(out, bits=11, downsample=1, mix_=0.25)

    # 7. Провалы связи
    if profile.dropout_count:
        out = dsp.dropouts(out, rng, count=profile.dropout_count, depth=0.18)

    # Повторный полосовой — сатурация всегда «размазывает» спектр наружу
    out = dsp.steep_bandpass(out, profile.band_low, profile.band_high, 2)
    return out


def phone_channel(sig: Signal, profile: VoiceProfile, emotion: Emotion,
                  rng: random.Random) -> Signal:
    """Телефонная линия звонящего: узкая полоса, кодек, лёгкие потери пакетов."""
    out = dsp.steep_bandpass(sig, profile.band_low, profile.band_high, profile.band_order)
    out = dsp.chain(
        out,
        dsp.peaking(1800.0, 1.0, profile.presence_db + emotion.presence_db),
        dsp.peaking(800.0, 0.9, 2.0),
        dsp.peaking(300.0, 0.8, profile.body_db),
    )
    out = dsp.compressor(out,
                         threshold_db=profile.comp_threshold - emotion.comp_extra,
                         ratio=profile.comp_ratio + emotion.comp_extra * 0.3,
                         attack_ms=6.0, release_ms=110.0, knee_db=6.0)
    out = dsp.saturate(out, drive=profile.drive * emotion.drive_mul,
                       kind=profile.sat_kind, mix_=0.85)
    out = dsp.mulaw(out, mu=255.0, mix_=0.7)
    out = dsp.bitcrush(out, bits=12, downsample=1, mix_=0.2)
    if profile.dropout_count:
        out = dsp.dropouts(out, rng, count=profile.dropout_count, min_ms=8.0,
                           max_ms=28.0, depth=0.25)
    out = dsp.steep_bandpass(out, profile.band_low, profile.band_high, 2)
    return out


def headset_channel(sig: Signal, profile: VoiceProfile, emotion: Emotion,
                    rng: random.Random) -> Signal:
    """Гарнитура оператора: чисто, широко, чуть студийной плотности."""
    out = dsp.chain(
        sig,
        dsp.highpass(profile.band_low, 0.7),
        dsp.lowpass(profile.band_high, 0.7),
        dsp.peaking(180.0, 0.8, profile.body_db),
        dsp.peaking(3000.0, 1.2, profile.presence_db),
        dsp.peaking(600.0, 1.0, -1.5),          # убрать «картон»
        dsp.highshelf(7000.0, 1.5),
    )
    out = dsp.deesser(out, 6800.0, -28.0, 3.5)
    out = dsp.compressor(out, threshold_db=profile.comp_threshold - emotion.comp_extra,
                         ratio=profile.comp_ratio, attack_ms=8.0, release_ms=120.0,
                         knee_db=8.0)
    out = dsp.saturate(out, drive=profile.drive, kind="tanh", mix_=0.5)
    return out


# ---------------------------------------------------------------------------
# Полный рендер
# ---------------------------------------------------------------------------

def render_line(raw: Signal, profile: VoiceProfile, emotion_name: str,
                seed: int, mode: str = "radio", ambience: str | None = None,
                ambience_db: float = -36.0) -> Signal:
    """
    mode: "radio"    — переговоры экипажей (PTT, squelch, roger-beep)
          "chatter"  — фоновый эфир (тише, без кликов, длиннее хвост)
          "phone"    — звонящий в 112 (телефонная линия + фон места)
          "headset"  — оператор 112 (чистая гарнитура)
    """
    rng = random.Random(seed)
    emotion = get_emotion(emotion_name)

    sig = dsp.trim_silence(raw, -46.0, 0.02)
    if not len(sig):
        return dsp.silence(0.4)

    # --- 1. Актёрский слой
    sig = dsp.deesser(sig, 6500.0, -26.0, 4.0)
    sig = dsp.gate(sig, threshold_db=-52.0, floor_db=-26.0)
    sig = apply_tremor(sig, emotion.tremor, emotion.tremor_hz, rng)
    sig = add_breath(sig, emotion.breath, rng)
    if mode in ("phone", "radio"):
        sig = add_breath_pauses(sig, emotion.breath, rng)

    # --- 2. Анатомия голоса персонажа
    if abs(profile.varispeed - 1.0) > 1e-3:
        sig = dsp.varispeed(sig, profile.varispeed)
    sig = dsp.formant_tilt(sig, profile.formant)

    # --- 3. Подача по громкости
    sig = dsp.gain_db(sig, emotion.volume_db * 0.6)

    # --- 4. Тракт канала
    if mode == "headset":
        sig = headset_channel(sig, profile, emotion, rng)
    elif mode == "phone":
        sig = phone_channel(sig, profile, emotion, rng)
    else:
        sig = radio_channel(sig, profile, emotion, rng)

    # --- 5. Фон места события / эфирная подложка
    body_len = len(sig)
    if mode in ("radio", "chatter"):
        bed = dsp.radio_hiss(body_len, rng, profile.hiss_db)
        bed = dsp.mix(bed, dsp.crackle(body_len, rng, 2.0, profile.crackle_db))
        bed = dsp.duck_by_speech(bed, sig, depth=0.45)
        sig = dsp.mix(sig, bed)
    elif mode == "phone":
        bed = dsp.radio_hiss(body_len, rng, profile.hiss_db)
        if ambience:
            room = dsp.room_tone(body_len, rng, ambience, ambience_db)
            room = dsp.steep_bandpass(room, profile.band_low, profile.band_high, 2)
            bed = dsp.mix(bed, room)
        bed = dsp.duck_by_speech(bed, sig, depth=0.35)
        sig = dsp.mix(sig, bed)

    # --- 6. Монтаж эфирных элементов
    if mode == "radio":
        press, release = fx.load_or_make_ptt(rng)
        parts = [dsp.gain_db(press, -2.0), dsp.silence(0.045), sig]
        if profile.roger_beep:
            parts.append(fx.roger_beep(rng))
        parts.extend([dsp.silence(0.02), dsp.gain_db(release, -3.0)])
        sig = dsp.concat(*parts)
    elif mode == "chatter":
        sig = dsp.concat(dsp.gain_db(fx.squelch_tail(rng, 0.08), -6.0),
                         sig,
                         dsp.gain_db(fx.squelch_tail(rng, 0.18), -4.0))
        sig = dsp.fade_in(dsp.fade_out(sig, 0.06), 0.04)
    elif mode == "phone":
        sig = dsp.concat(dsp.silence(0.03), sig, dsp.silence(0.05))
    else:  # headset
        sig = dsp.concat(dsp.silence(0.02), sig, dsp.silence(0.04))

    # --- 7. Мастеринг реплики
    sig = dsp.normalize(sig, profile.target_rms_db, -1.5)
    sig = dsp.limiter(sig, ceiling_db=-1.0, lookahead_ms=2.0, release_ms=50.0)
    sig = dsp.fade_in(dsp.fade_out(sig, 0.012), 0.004)
    return sig


def render_silence_clip(seconds: float = 1.0) -> Signal:
    """Клип-пауза для реплик без текста (молчание, гудки, сброс вызова)."""
    return dsp.silence(seconds)


def render_hangup(seed: int = 0) -> Signal:
    """Короткие гудки отбоя — когда звонящий бросает трубку."""
    rng = random.Random(seed)
    out = dsp.new_signal(0)
    for _ in range(3):
        beep = dsp.new_signal(int(0.35 * SR))
        for i in range(len(beep)):
            beep[i] = math.sin(2 * math.pi * 425.0 * i / SR) * 0.35
        beep = dsp.fade_in(dsp.fade_out(beep, 0.01), 0.01)
        out = dsp.concat(out, beep, dsp.silence(0.35))
    out = dsp.steep_bandpass(out, 300.0, 3400.0, 3)
    return dsp.limiter(dsp.normalize(out, -20.0, -3.0), -3.0)
