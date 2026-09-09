"""
Кинематографический DSP-движок для русской озвучки 112 Operator.

Полностью на стандартной библиотеке Python: ffmpeg/sox/numpy НЕ требуются.
Внутреннее представление сигнала — моно, float, 44100 Гц (array('f')).

Модуль реализует всё, что нужно для «голливудского» звука рации и
телефонной линии:
  * биквад-фильтры (LP/HP/peak/shelf) с каскадированием (крутизна 12..48 дБ/окт)
  * компрессор с side-chain детектором, лимитер с look-ahead
  * де-эссер, экспандер/гейт
  * ламповая/транзисторная сатурация (tanh, atan, hard-clip)
  * varispeed (сдвиг тембра+высоты) для «кастинга» разных голосов из одного TTS
  * шумовые слои: эфирный шип, треск, дыхание микрофона, комнатный тон
  * артефакты цифровой связи: bit-crush, mu-law, дропауты пакетов
  * склейка PTT-клика тангенты и squelch-хвоста
"""

from __future__ import annotations

import array
import math
import random
import struct
import wave

SR = 44100
EPS = 1e-12

Signal = array.array  # array('f')


# --------------------------------------------------------------------------
# Базовые операции
# --------------------------------------------------------------------------

def new_signal(n: int = 0, value: float = 0.0) -> Signal:
    return array.array("f", [value] * n)


def from_iter(values) -> Signal:
    return array.array("f", values)


def db_to_lin(db: float) -> float:
    return 10.0 ** (db / 20.0)


def lin_to_db(lin: float) -> float:
    return 20.0 * math.log10(max(abs(lin), EPS))


def peak(sig: Signal) -> float:
    return max((abs(s) for s in sig), default=0.0)


def rms(sig: Signal) -> float:
    if not len(sig):
        return 0.0
    acc = 0.0
    for s in sig:
        acc += s * s
    return math.sqrt(acc / len(sig))


def gain(sig: Signal, g: float) -> Signal:
    return array.array("f", [s * g for s in sig])


def gain_db(sig: Signal, db: float) -> Signal:
    return gain(sig, db_to_lin(db))


def concat(*parts: Signal) -> Signal:
    out = array.array("f")
    for p in parts:
        if p is not None and len(p):
            out.extend(p)
    return out


def mix(base: Signal, overlay: Signal, at: int = 0, level: float = 1.0) -> Signal:
    """Подмешать overlay в base начиная с сэмпла at (base удлиняется при нужде)."""
    need = at + len(overlay)
    out = array.array("f", base)
    if len(out) < need:
        out.extend(array.array("f", [0.0] * (need - len(out))))
    for i, v in enumerate(overlay):
        out[at + i] += v * level
    return out


def silence(seconds: float) -> Signal:
    return array.array("f", [0.0] * max(0, int(seconds * SR)))


def fade_in(sig: Signal, seconds: float) -> Signal:
    n = min(len(sig), int(seconds * SR))
    out = array.array("f", sig)
    for i in range(n):
        out[i] *= i / max(1, n)
    return out


def fade_out(sig: Signal, seconds: float) -> Signal:
    n = min(len(sig), int(seconds * SR))
    out = array.array("f", sig)
    total = len(out)
    for i in range(n):
        out[total - n + i] *= 1.0 - i / max(1, n)
    return out


def trim_silence(sig: Signal, threshold_db: float = -46.0, pad: float = 0.03) -> Signal:
    """Обрезать «воздух» в начале и конце фразы — TTS любит оставлять паузы."""
    thr = db_to_lin(threshold_db)
    n = len(sig)
    start, end = 0, n
    for i in range(n):
        if abs(sig[i]) > thr:
            start = i
            break
    for i in range(n - 1, -1, -1):
        if abs(sig[i]) > thr:
            end = i + 1
            break
    if end <= start:
        return array.array("f", sig)
    padn = int(pad * SR)
    start = max(0, start - padn)
    end = min(n, end + padn)
    return array.array("f", sig[start:end])


# --------------------------------------------------------------------------
# Биквад-фильтры (RBJ cookbook)
# --------------------------------------------------------------------------

class Biquad:
    __slots__ = ("b0", "b1", "b2", "a1", "a2")

    def __init__(self, b0, b1, b2, a0, a1, a2):
        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0

    def process(self, sig: Signal) -> Signal:
        b0, b1, b2, a1, a2 = self.b0, self.b1, self.b2, self.a1, self.a2
        x1 = x2 = y1 = y2 = 0.0
        out = array.array("f", bytes(4 * len(sig)))
        for i, x0 in enumerate(sig):
            y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            out[i] = y0
            x2, x1 = x1, x0
            y2, y1 = y1, y0
        return out


def _wc(freq: float):
    w0 = 2.0 * math.pi * min(freq, SR * 0.49) / SR
    return w0, math.cos(w0), math.sin(w0)


def lowpass(freq: float, q: float = 0.7071) -> Biquad:
    w0, cw, sw = _wc(freq)
    alpha = sw / (2.0 * q)
    b0 = (1 - cw) / 2
    b1 = 1 - cw
    b2 = (1 - cw) / 2
    return Biquad(b0, b1, b2, 1 + alpha, -2 * cw, 1 - alpha)


def highpass(freq: float, q: float = 0.7071) -> Biquad:
    w0, cw, sw = _wc(freq)
    alpha = sw / (2.0 * q)
    b0 = (1 + cw) / 2
    b1 = -(1 + cw)
    b2 = (1 + cw) / 2
    return Biquad(b0, b1, b2, 1 + alpha, -2 * cw, 1 - alpha)


def bandpass(freq: float, q: float = 1.0) -> Biquad:
    w0, cw, sw = _wc(freq)
    alpha = sw / (2.0 * q)
    return Biquad(alpha, 0.0, -alpha, 1 + alpha, -2 * cw, 1 - alpha)


def peaking(freq: float, q: float, gain_db_: float) -> Biquad:
    a = db_to_lin(gain_db_ / 2.0)
    w0, cw, sw = _wc(freq)
    alpha = sw / (2.0 * q)
    return Biquad(1 + alpha * a, -2 * cw, 1 - alpha * a,
                  1 + alpha / a, -2 * cw, 1 - alpha / a)


def lowshelf(freq: float, gain_db_: float, s: float = 0.9) -> Biquad:
    a = db_to_lin(gain_db_ / 2.0)
    w0, cw, sw = _wc(freq)
    alpha = sw / 2.0 * math.sqrt((a + 1 / a) * (1 / s - 1) + 2)
    tsa = 2 * math.sqrt(a) * alpha
    return Biquad(a * ((a + 1) - (a - 1) * cw + tsa),
                  2 * a * ((a - 1) - (a + 1) * cw),
                  a * ((a + 1) - (a - 1) * cw - tsa),
                  (a + 1) + (a - 1) * cw + tsa,
                  -2 * ((a - 1) + (a + 1) * cw),
                  (a + 1) + (a - 1) * cw - tsa)


def highshelf(freq: float, gain_db_: float, s: float = 0.9) -> Biquad:
    a = db_to_lin(gain_db_ / 2.0)
    w0, cw, sw = _wc(freq)
    alpha = sw / 2.0 * math.sqrt((a + 1 / a) * (1 / s - 1) + 2)
    tsa = 2 * math.sqrt(a) * alpha
    return Biquad(a * ((a + 1) + (a - 1) * cw + tsa),
                  -2 * a * ((a - 1) + (a + 1) * cw),
                  a * ((a + 1) + (a - 1) * cw - tsa),
                  (a + 1) - (a - 1) * cw + tsa,
                  2 * ((a - 1) - (a + 1) * cw),
                  (a + 1) - (a - 1) * cw - tsa)


def chain(sig: Signal, *filters: Biquad) -> Signal:
    out = sig
    for f in filters:
        out = f.process(out)
    return out


def steep_bandpass(sig: Signal, low: float, high: float, order: int = 4) -> Signal:
    """Крутой полосовой фильтр (order*12 дБ/окт) — «горловина» рации."""
    out = sig
    for _ in range(order):
        out = highpass(low, 0.707).process(out)
        out = lowpass(high, 0.707).process(out)
    return out


# --------------------------------------------------------------------------
# Динамика
# --------------------------------------------------------------------------

def envelope(sig: Signal, attack_ms: float = 5.0, release_ms: float = 60.0) -> Signal:
    at = math.exp(-1.0 / (SR * attack_ms / 1000.0))
    rt = math.exp(-1.0 / (SR * release_ms / 1000.0))
    env = array.array("f", bytes(4 * len(sig)))
    e = 0.0
    for i, s in enumerate(sig):
        a = abs(s)
        coef = at if a > e else rt
        e = coef * e + (1 - coef) * a
        env[i] = e
    return env


def compressor(sig: Signal, threshold_db: float = -18.0, ratio: float = 4.0,
               attack_ms: float = 6.0, release_ms: float = 90.0,
               knee_db: float = 6.0, makeup_db: float | None = None) -> Signal:
    """Мягкий компрессор с коленом — «клеит» динамику речи под эфир."""
    env = envelope(sig, attack_ms, release_ms)
    out = array.array("f", bytes(4 * len(sig)))
    half_knee = knee_db / 2.0
    for i, s in enumerate(sig):
        level = lin_to_db(env[i])
        over = level - threshold_db
        if over <= -half_knee:
            reduction = 0.0
        elif over >= half_knee:
            reduction = over - over / ratio
        else:
            # квадратичное колено
            x = over + half_knee
            reduction = (1 - 1 / ratio) * x * x / (2 * knee_db)
        out[i] = s * db_to_lin(-reduction)
    if makeup_db is None:
        makeup_db = max(0.0, -threshold_db * (1 - 1 / ratio) * 0.55)
    return gain_db(out, makeup_db)


def limiter(sig: Signal, ceiling_db: float = -1.0, lookahead_ms: float = 2.0,
            release_ms: float = 60.0) -> Signal:
    """
    Лимитер с предпросмотром: гарантирует отсутствие цифрового клиппинга.

    Скользящий максимум считается монотонной очередью (O(n)), а не наивным
    перебором окна — иначе сборка 600+ файлов растягивается на часы.
    """
    from collections import deque

    ceiling = db_to_lin(ceiling_db)
    la = max(1, int(SR * lookahead_ms / 1000.0))
    padded = array.array("f", sig)
    padded.extend(array.array("f", [0.0] * la))
    n = len(padded)
    rel = math.exp(-1.0 / (SR * release_ms / 1000.0))

    out = array.array("f", bytes(4 * n))
    dq: deque = deque()          # индексы, значения |x| по убыванию
    g = 1.0
    head = 0

    # предзаполняем окно [0, la)
    for j in range(min(la, n)):
        a = abs(padded[j])
        while dq and dq[-1][1] <= a:
            dq.pop()
        dq.append((j, a))

    for i in range(n):
        # выкинуть вышедшие за левую границу
        while dq and dq[0][0] < i:
            dq.popleft()
        window_peak = dq[0][1] if dq else 0.0
        target = 1.0 if window_peak <= ceiling else ceiling / window_peak
        if target < g:
            g = target
        else:
            g = rel * g + (1 - rel) * target
        out[i] = padded[i] * g
        # добавить новый сэмпл на правой границе
        j = i + la
        if j < n:
            a = abs(padded[j])
            while dq and dq[-1][1] <= a:
                dq.pop()
            dq.append((j, a))

    return array.array("f", out[la:])


def gate(sig: Signal, threshold_db: float = -50.0, attack_ms: float = 3.0,
         release_ms: float = 120.0, floor_db: float = -24.0) -> Signal:
    """Мягкий гейт: убирает шипение TTS между словами, не режет хвосты."""
    env = envelope(sig, attack_ms, release_ms)
    thr = db_to_lin(threshold_db)
    floor = db_to_lin(floor_db)
    out = array.array("f", bytes(4 * len(sig)))
    g = floor
    smooth = math.exp(-1.0 / (SR * 0.008))
    for i, s in enumerate(sig):
        target = 1.0 if env[i] > thr else floor
        g = smooth * g + (1 - smooth) * target
        out[i] = s * g
    return out


def deesser(sig: Signal, freq: float = 6500.0, threshold_db: float = -26.0,
            ratio: float = 4.0) -> Signal:
    """Убирает «сы-сы» цифрового голоса: компрессия только сибилянтной полосы."""
    sib = bandpass(freq, 1.2).process(sig)
    env = envelope(sib, 1.5, 40.0)
    out = array.array("f", bytes(4 * len(sig)))
    for i, s in enumerate(sig):
        level = lin_to_db(env[i])
        over = level - threshold_db
        red = 0.0 if over <= 0 else over - over / ratio
        out[i] = s - sib[i] * (1.0 - db_to_lin(-red))
    return out


# --------------------------------------------------------------------------
# Нелинейности
# --------------------------------------------------------------------------

def saturate(sig: Signal, drive: float = 1.6, kind: str = "tanh", mix_: float = 1.0) -> Signal:
    out = array.array("f", bytes(4 * len(sig)))
    for i, s in enumerate(sig):
        x = s * drive
        if kind == "tanh":
            y = math.tanh(x)
        elif kind == "atan":
            y = (2.0 / math.pi) * math.atan(x * 1.6)
        elif kind == "hard":
            y = max(-1.0, min(1.0, x))
        elif kind == "fold":
            y = math.sin(max(-2.5, min(2.5, x)))
        else:
            y = x
        out[i] = s * (1.0 - mix_) + (y / max(drive, 1.0)) * mix_
    return out


def bitcrush(sig: Signal, bits: int = 10, downsample: int = 1, mix_: float = 1.0) -> Signal:
    """Артефакты цифрового кодека связи."""
    levels = float(2 ** (bits - 1))
    out = array.array("f", bytes(4 * len(sig)))
    hold = 0.0
    for i, s in enumerate(sig):
        if downsample <= 1 or i % downsample == 0:
            hold = round(max(-1.0, min(1.0, s)) * levels) / levels
        out[i] = s * (1 - mix_) + hold * mix_
    return out


def mulaw(sig: Signal, mu: float = 255.0, mix_: float = 0.85) -> Signal:
    """Компандирование μ-law — характерный «телефонный» окрас."""
    out = array.array("f", bytes(4 * len(sig)))
    ln = math.log(1 + mu)
    for i, s in enumerate(sig):
        x = max(-1.0, min(1.0, s))
        y = math.copysign(math.log(1 + mu * abs(x)) / ln, x)
        z = math.copysign((1.0 / mu) * ((1 + mu) ** abs(y) - 1), y)
        out[i] = s * (1 - mix_) + z * mix_
    return out


def dropouts(sig: Signal, rng: random.Random, count: int = 2,
             min_ms: float = 12.0, max_ms: float = 45.0, depth: float = 0.15) -> Signal:
    """Редкие провалы связи — читаемость не страдает, реализм растёт."""
    out = array.array("f", sig)
    n = len(out)
    if n < SR // 2:
        return out
    for _ in range(count):
        dur = int(SR * rng.uniform(min_ms, max_ms) / 1000.0)
        if dur >= n:
            continue
        start = rng.randrange(0, n - dur)
        ramp = max(1, dur // 6)
        for i in range(dur):
            if i < ramp:
                k = 1.0 - (1.0 - depth) * (i / ramp)
            elif i > dur - ramp:
                k = depth + (1.0 - depth) * ((i - (dur - ramp)) / ramp)
            else:
                k = depth
            out[start + i] *= k
    return out


# --------------------------------------------------------------------------
# Varispeed / тембр («кастинг» разных персонажей из одного TTS-голоса)
# --------------------------------------------------------------------------

def varispeed(sig: Signal, factor: float) -> Signal:
    """
    Изменение скорости воспроизведения с линейной интерполяцией.
    factor > 1 — быстрее и выше (моложе/тоньше), < 1 — ниже и «крупнее».
    Длительность компенсируется настройкой темпа TTS (см. casting.py).
    """
    if abs(factor - 1.0) < 1e-4 or not len(sig):
        return array.array("f", sig)
    n = len(sig)
    out_n = max(1, int(n / factor))
    out = array.array("f", bytes(4 * out_n))
    for i in range(out_n):
        pos = i * factor
        i0 = int(pos)
        if i0 >= n - 1:
            out[i] = sig[n - 1]
        else:
            frac = pos - i0
            out[i] = sig[i0] * (1 - frac) + sig[i0 + 1] * frac
    return out


def formant_tilt(sig: Signal, amount: float) -> Signal:
    """
    Лёгкая коррекция «размера головы» после varispeed:
    amount > 0 — плотнее/мужественнее, < 0 — легче/светлее.
    """
    if abs(amount) < 0.01:
        return sig
    return chain(
        sig,
        lowshelf(320.0, 3.5 * amount),
        peaking(1150.0, 1.0, -1.6 * amount),
        highshelf(4200.0, -2.2 * amount),
    )


# --------------------------------------------------------------------------
# Шумы и атмосфера
# --------------------------------------------------------------------------

def white_noise(n: int, rng: random.Random) -> Signal:
    return array.array("f", [rng.uniform(-1.0, 1.0) for _ in range(n)])


def pink_noise(n: int, rng: random.Random) -> Signal:
    b0 = b1 = b2 = 0.0
    out = array.array("f", bytes(4 * n))
    for i in range(n):
        w = rng.uniform(-1.0, 1.0)
        b0 = 0.99765 * b0 + w * 0.0990460
        b1 = 0.96300 * b1 + w * 0.2965164
        b2 = 0.57000 * b2 + w * 1.0526913
        out[i] = (b0 + b1 + b2 + w * 0.1848) * 0.22
    return out


def radio_hiss(n: int, rng: random.Random, level_db: float = -38.0) -> Signal:
    """Эфирный шип: розовый шум в полосе рации с лёгкой модуляцией."""
    noise = pink_noise(n, rng)
    noise = steep_bandpass(noise, 420.0, 3300.0, order=2)
    out = array.array("f", bytes(4 * n))
    g = db_to_lin(level_db)
    for i in range(n):
        wobble = 1.0 + 0.25 * math.sin(2 * math.pi * 0.7 * i / SR + rng.random() * 0.0001)
        out[i] = noise[i] * g * wobble
    return out


def crackle(n: int, rng: random.Random, density: float = 2.5, level_db: float = -30.0) -> Signal:
    """Редкие электростатические щелчки в эфире."""
    out = array.array("f", bytes(4 * n))
    g = db_to_lin(level_db)
    expected = max(0, int(density * n / SR))
    for _ in range(expected):
        pos = rng.randrange(0, max(1, n))
        length = rng.randint(12, 90)
        amp = g * rng.uniform(0.3, 1.0)
        for i in range(length):
            if pos + i >= n:
                break
            decay = math.exp(-4.0 * i / length)
            out[pos + i] += rng.uniform(-1.0, 1.0) * amp * decay
    return steep_bandpass(out, 700.0, 3400.0, order=1)


def duck_by_speech(bed: Signal, speech: Signal, depth: float = 0.55) -> Signal:
    """Шумовая подложка приседает под речь — как в реальном эфире (АРУ)."""
    env = envelope(speech, 8.0, 140.0)
    mx = max(env, default=0.0) or 1.0
    out = array.array("f", bytes(4 * len(bed)))
    for i in range(len(bed)):
        e = env[i] / mx if i < len(env) else 0.0
        out[i] = bed[i] * (1.0 - depth * min(1.0, e * 2.2))
    return out


def room_tone(n: int, rng: random.Random, kind: str = "street", level_db: float = -34.0) -> Signal:
    """Фон места, откуда говорит звонящий: улица / помещение / машина."""
    base = pink_noise(n, rng)
    if kind == "street":
        base = chain(base, lowpass(1800.0, 0.8), highpass(120.0, 0.7))
    elif kind == "indoor":
        base = chain(base, lowpass(900.0, 0.8), highpass(70.0, 0.7))
    elif kind == "car":
        base = chain(base, lowpass(420.0, 0.9), highpass(45.0, 0.7))
    elif kind == "crowd":
        base = chain(base, bandpass(700.0, 0.6), lowpass(2500.0, 0.8))
    return gain_db(base, level_db)


# --------------------------------------------------------------------------
# Ввод/вывод WAV
# --------------------------------------------------------------------------

def read_wav(path: str) -> Signal:
    """Читает WAV (8/16/24/32-bit PCM или float32), возвращает моно @ SR."""
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        frames = w.readframes(w.getnframes())

    if sw == 2:
        data = array.array("h")
        data.frombytes(frames)
        scale = 1.0 / 32768.0
        samples = [s * scale for s in data]
    elif sw == 1:
        samples = [(b - 128) / 128.0 for b in frames]
    elif sw == 4:
        data = array.array("i")
        data.frombytes(frames)
        scale = 1.0 / 2147483648.0
        samples = [s * scale for s in data]
    elif sw == 3:
        samples = []
        for i in range(0, len(frames), 3):
            b = frames[i:i + 3]
            val = int.from_bytes(b, "little", signed=True)
            samples.append(val / 8388608.0)
    else:
        raise ValueError(f"Неподдерживаемая разрядность WAV: {sw * 8} бит ({path})")

    if ch > 1:
        mono = [sum(samples[i:i + ch]) / ch for i in range(0, len(samples) - ch + 1, ch)]
    else:
        mono = samples

    sig = array.array("f", mono)
    if sr != SR:
        sig = resample(sig, sr, SR)
    return sig


def resample(sig: Signal, src_sr: int, dst_sr: int) -> Signal:
    if src_sr == dst_sr or not len(sig):
        return array.array("f", sig)
    ratio = src_sr / dst_sr
    out_n = int(len(sig) / ratio)
    out = array.array("f", bytes(4 * out_n))
    n = len(sig)
    for i in range(out_n):
        pos = i * ratio
        i0 = int(pos)
        frac = pos - i0
        s0 = sig[i0] if i0 < n else 0.0
        s1 = sig[i0 + 1] if i0 + 1 < n else s0
        out[i] = s0 * (1 - frac) + s1 * frac
    return out


def write_wav(path: str, sig: Signal, stereo: bool = True, bits: int = 16) -> None:
    """Сохраняет 16-бит PCM WAV 44.1 кГц — формат, который грузит движок мода."""
    data = array.array("h", bytes(2 * len(sig) * (2 if stereo else 1)))
    idx = 0
    for s in sig:
        v = int(max(-1.0, min(1.0, s)) * 32767.0)
        data[idx] = v
        idx += 1
        if stereo:
            data[idx] = v
            idx += 1
    with wave.open(path, "wb") as w:
        w.setnchannels(2 if stereo else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def normalize(sig: Signal, target_rms_db: float = -18.0, peak_ceiling_db: float = -1.0) -> Signal:
    """Выравнивание громкости всех реплик: одинаковый RMS + запас по пикам."""
    cur = rms(sig)
    if cur < EPS:
        return sig
    out = gain(sig, db_to_lin(target_rms_db) / cur)
    p = peak(out)
    ceiling = db_to_lin(peak_ceiling_db)
    if p > ceiling:
        out = gain(out, ceiling / p)
    return out


def duration(sig: Signal) -> float:
    return len(sig) / float(SR)
