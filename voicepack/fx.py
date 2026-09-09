"""
Процедурный синтез эфирных эффектов рации и телефонной линии.

Все эффекты генерируются кодом (ffmpeg/сэмплы не нужны), поэтому пак
воспроизводим побитово при одном и том же seed. Если в fx/ лежат
пользовательские сэмплы ptt_start.wav / ptt_end.wav — они используются
как основа, а синтез служит запасным вариантом и «дожимает» характер.
"""

from __future__ import annotations

import math
import os
import random

from . import dsp
from .dsp import SR, Signal

FX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fx")


# --------------------------------------------------------------------------
# Элементарные генераторы
# --------------------------------------------------------------------------

def _tone(freq: float, seconds: float, amp: float = 0.5,
          decay: float = 0.0, shape: str = "sine") -> Signal:
    n = int(seconds * SR)
    out = dsp.new_signal(n)
    for i in range(n):
        t = i / SR
        ph = 2 * math.pi * freq * t
        if shape == "sine":
            v = math.sin(ph)
        elif shape == "square":
            v = 1.0 if math.sin(ph) >= 0 else -1.0
        else:
            v = math.sin(ph)
        env = math.exp(-decay * t) if decay else 1.0
        out[i] = v * amp * env
    return out


def _click(rng: random.Random, brightness: float = 1.0, amp: float = 0.6,
           length_ms: float = 18.0) -> Signal:
    """Электромеханический щелчок тангенты: импульс шума + резонанс реле."""
    n = int(SR * length_ms / 1000.0)
    sig = dsp.new_signal(n)
    for i in range(n):
        t = i / n
        sig[i] = rng.uniform(-1.0, 1.0) * math.exp(-9.0 * t)
    sig = dsp.chain(
        sig,
        dsp.bandpass(1400.0 * brightness, 0.9),
        dsp.peaking(2600.0 * brightness, 2.0, 6.0),
        dsp.highpass(380.0, 0.7),
    )
    return dsp.gain(dsp.normalize(sig, -14.0, -3.0), amp)


# --------------------------------------------------------------------------
# Готовые эфирные элементы
# --------------------------------------------------------------------------

def ptt_press(rng: random.Random) -> Signal:
    """Нажатие тангенты: щелчок + короткий всплеск шумоподавителя."""
    click = _click(rng, brightness=1.0, amp=0.55, length_ms=16.0)
    burst_n = int(0.05 * SR)
    burst = dsp.white_noise(burst_n, rng)
    burst = dsp.steep_bandpass(burst, 900.0, 3300.0, order=2)
    for i in range(burst_n):
        burst[i] *= math.exp(-14.0 * i / burst_n) * 0.28
    return dsp.limiter(dsp.concat(click, burst), -2.0)


def ptt_release(rng: random.Random) -> Signal:
    """Отпускание тангенты: squelch-хвост «пшшш» + двойной щелчок реле."""
    tail_n = int(0.11 * SR)
    tail = dsp.white_noise(tail_n, rng)
    tail = dsp.steep_bandpass(tail, 700.0, 3600.0, order=2)
    for i in range(tail_n):
        t = i / tail_n
        tail[i] *= (math.exp(-6.5 * t)) * 0.34
    click = _click(rng, brightness=0.85, amp=0.42, length_ms=13.0)
    return dsp.limiter(dsp.concat(tail, click), -2.0)


def roger_beep(rng: random.Random, freq: float = 1180.0) -> Signal:
    """Короткий «роджер-бип» конца передачи (как в тактических радиостанциях)."""
    beep = _tone(freq, 0.075, amp=0.22, decay=6.0)
    beep = dsp.fade_in(dsp.fade_out(beep, 0.02), 0.005)
    return beep


def squelch_tail(rng: random.Random, seconds: float = 0.16) -> Signal:
    n = int(seconds * SR)
    tail = dsp.pink_noise(n, rng)
    tail = dsp.steep_bandpass(tail, 600.0, 3400.0, order=2)
    for i in range(n):
        tail[i] *= math.exp(-7.0 * i / n) * 0.3
    return tail


def dial_tone_blip(rng: random.Random) -> Signal:
    """Короткий сигнал коммутации перед соединением звонка."""
    a = _tone(425.0, 0.05, amp=0.10, decay=10.0)
    return dsp.fade_out(dsp.fade_in(a, 0.005), 0.02)


def load_or_make_ptt(rng: random.Random) -> tuple[Signal, Signal]:
    """Берёт пользовательские fx/ptt_*.wav если они есть, иначе синтезирует."""
    start_path = os.path.join(FX_DIR, "ptt_start.wav")
    end_path = os.path.join(FX_DIR, "ptt_end.wav")
    try:
        if os.path.exists(start_path) and os.path.exists(end_path):
            start = dsp.normalize(dsp.read_wav(start_path), -20.0, -3.0)
            end = dsp.normalize(dsp.read_wav(end_path), -20.0, -3.0)
            # Дожимаем характер: даже пользовательские клики проходят полосу рации
            start = dsp.steep_bandpass(start, 400.0, 3600.0, order=1)
            end = dsp.steep_bandpass(end, 400.0, 3600.0, order=1)
            return start, end
    except Exception:
        pass
    return ptt_press(rng), ptt_release(rng)
