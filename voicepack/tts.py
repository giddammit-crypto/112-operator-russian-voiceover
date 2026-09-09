"""
Слой синтеза речи с несколькими взаимозаменяемыми бэкендами.

Порядок выбора (первый доступный):
  1. edge   — Microsoft Edge TTS (ru-RU-DmitryNeural / SvetlanaNeural),
              нейронные голоса без иностранного акцента, поддержка SSML-стилей.
  2. piper  — локальный Piper с русской моделью (полностью офлайн).
  3. silero — Silero TTS v4 (torch), офлайн, русские дикторы aidar/baya/eugene/kseniya.
  4. espeak — espeak-ng, только как аварийный вариант (разборчиво, но роботно).
  5. stub   — встроенный процедурный вокализатор: голоса нет, но пайплайн,
              длительности и DSP проверяются без сети (режим --dry-run/тестов).

Бэкенд возвращает моно-сигнал 44100 Гц (array('f')) — дальше им занимается render.py.
"""

from __future__ import annotations

import asyncio
import math
import os
import random
import shutil
import subprocess
import tempfile

from . import dsp
from .dsp import SR, Signal


class TTSError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Базовый интерфейс
# ---------------------------------------------------------------------------

class Backend:
    name = "base"
    supports_styles = False

    def available(self) -> bool:
        return False

    def synth(self, text: str, voice: str, rate: float, pitch_semitones: float,
              style: str = "", style_degree: float = 1.0) -> Signal:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1. Edge TTS
# ---------------------------------------------------------------------------

class EdgeBackend(Backend):
    name = "edge"
    supports_styles = False  # публичный endpoint игнорирует mstts:express-as

    def __init__(self):
        self._mod = None
        self._checked = False
        self._ok = False

    def _load(self):
        if self._mod is None:
            try:
                import edge_tts  # type: ignore
                self._mod = edge_tts
            except Exception:
                self._mod = False
        return self._mod

    def available(self) -> bool:
        if self._checked:
            return self._ok
        self._checked = True
        mod = self._load()
        if not mod:
            self._ok = False
            return False
        # Проверяем реальную сетевую доступность сервиса
        async def probe():
            try:
                loop = asyncio.get_running_loop()
                loop.set_exception_handler(lambda _loop, _ctx: None)
                comm = mod.Communicate(text="проверка связи", voice="ru-RU-DmitryNeural")
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        return True
                return False
            except Exception:
                return False
        try:
            self._ok = asyncio.run(asyncio.wait_for(probe(), timeout=25))
        except Exception:
            self._ok = False
        return self._ok

    @staticmethod
    def _pct(value: float) -> str:
        pct = int(round((value - 1.0) * 100))
        return f"{pct:+d}%"

    @staticmethod
    def _hz(semitones: float) -> str:
        # Edge принимает pitch в Гц; шкалируем полутона от базовых ~120 Гц
        hz = int(round(120.0 * (2 ** (semitones / 12.0) - 1.0)))
        return f"{hz:+d}Hz"

    def synth(self, text, voice, rate=1.0, pitch_semitones=0.0, style="", style_degree=1.0):
        mod = self._load()
        if not mod:
            raise TTSError("edge_tts не установлен")
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()

        async def run():
            loop = asyncio.get_running_loop()
            loop.set_exception_handler(lambda _loop, _ctx: None)
            comm = mod.Communicate(
                text=text,
                voice=voice,
                rate=self._pct(rate),
                pitch=self._hz(pitch_semitones),
            )
            await comm.save(tmp.name)

        try:
            asyncio.run(run())
            return decode_audio(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 2. Piper (офлайн)
# ---------------------------------------------------------------------------

class PiperBackend(Backend):
    name = "piper"

    def __init__(self, model_dir: str | None = None):
        self.bin = shutil.which("piper") or shutil.which("piper-tts")
        self.model_dir = model_dir or os.environ.get("PIPER_MODEL_DIR", "")
        self._models = {}

    def _find_model(self, voice: str) -> str | None:
        if not self.model_dir or not os.path.isdir(self.model_dir):
            return None
        female = "svetlana" in voice.lower() or "female" in voice.lower()
        cands = sorted(f for f in os.listdir(self.model_dir) if f.endswith(".onnx"))
        ru = [c for c in cands if c.startswith("ru")] or cands
        if not ru:
            return None
        # эвристика: модели с "irina"/"female" считаем женскими
        fem = [c for c in ru if any(k in c.lower() for k in ("irina", "female", "elena"))]
        male = [c for c in ru if c not in fem]
        pick = (fem or ru) if female else (male or ru)
        return os.path.join(self.model_dir, pick[0])

    def available(self) -> bool:
        return bool(self.bin) and self._find_model("ru-RU-DmitryNeural") is not None

    def synth(self, text, voice, rate=1.0, pitch_semitones=0.0, style="", style_degree=1.0):
        model = self._find_model(voice)
        if not model:
            raise TTSError("Не найдена модель Piper")
        out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        out.close()
        cmd = [self.bin, "--model", model, "--output_file", out.name,
               "--length_scale", f"{1.0 / max(rate, 0.1):.3f}"]
        try:
            subprocess.run(cmd, input=text.encode("utf-8"), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sig = dsp.read_wav(out.name)
            if abs(pitch_semitones) > 0.01:
                sig = _pitch_shift(sig, pitch_semitones)
            return sig
        finally:
            try:
                os.unlink(out.name)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 3. Silero (офлайн, torch)
# ---------------------------------------------------------------------------

class SileroBackend(Backend):
    name = "silero"

    VOICE_MAP = {
        "ru-RU-DmitryNeural": "aidar",
        "ru-RU-SvetlanaNeural": "baya",
        "male": "eugene",
        "female": "kseniya",
    }

    def __init__(self):
        self._model = None
        self._failed = False

    def _load(self):
        if self._model is not None or self._failed:
            return self._model
        try:
            import torch  # type: ignore
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts", language="ru", speaker="v4_ru",
                trust_repo=True,
            )
            model.to(torch.device("cpu"))
            self._model = model
        except Exception:
            self._failed = True
            self._model = None
        return self._model

    def available(self) -> bool:
        try:
            import torch  # noqa: F401
        except Exception:
            return False
        return self._load() is not None

    def synth(self, text, voice, rate=1.0, pitch_semitones=0.0, style="", style_degree=1.0):
        model = self._load()
        if model is None:
            raise TTSError("Silero недоступен")
        speaker = self.VOICE_MAP.get(voice, "aidar")
        audio = model.apply_tts(text=text, speaker=speaker, sample_rate=48000)
        sig = dsp.resample(dsp.from_iter(float(x) for x in audio), 48000, SR)
        if abs(rate - 1.0) > 0.01:
            sig = _time_stretch_via_varispeed(sig, rate)
        if abs(pitch_semitones) > 0.01:
            sig = _pitch_shift(sig, pitch_semitones)
        return sig


# ---------------------------------------------------------------------------
# 4. espeak-ng (аварийный)
# ---------------------------------------------------------------------------

class EspeakBackend(Backend):
    name = "espeak"

    def __init__(self):
        self.bin = shutil.which("espeak-ng") or shutil.which("espeak")

    def available(self) -> bool:
        return bool(self.bin)

    def synth(self, text, voice, rate=1.0, pitch_semitones=0.0, style="", style_degree=1.0):
        out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        out.close()
        female = "svetlana" in voice.lower()
        wpm = int(150 * rate)
        pitch = int(max(0, min(99, 50 + pitch_semitones * 4 + (12 if female else 0))))
        cmd = [self.bin, "-v", "ru+f3" if female else "ru", "-s", str(wpm),
               "-p", str(pitch), "-w", out.name, text]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return dsp.read_wav(out.name)
        finally:
            try:
                os.unlink(out.name)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 5. Процедурный стенд (без сети) — только для проверки пайплайна
# ---------------------------------------------------------------------------

class StubBackend(Backend):
    """
    Формантный «псевдоголос»: слогоподобная вокализация с реалистичной
    длительностью и интонацией. Слов не разобрать — это НЕ релизный звук,
    а способ прогнать весь тракт (DSP, склейку, тайминги) без сети.
    """

    name = "stub"

    VOWELS = [(700, 1100), (500, 1700), (350, 2100), (450, 900), (300, 800)]

    def available(self) -> bool:
        return True

    def synth(self, text, voice, rate=1.0, pitch_semitones=0.0, style="", style_degree=1.0):
        rng = random.Random(hash((text, voice)) & 0xFFFFFFFF)
        female = "svetlana" in voice.lower() or "female" in voice.lower()
        f0 = (190.0 if female else 112.0) * (2 ** (pitch_semitones / 12.0))

        words = [w for w in text.replace("\u00a0", " ").split() if w]
        out = dsp.new_signal(0)
        for wi, word in enumerate(words):
            syl = max(1, sum(1 for c in word.lower() if c in "аеёиоуыэюяaeiouy"))
            for s in range(syl):
                dur = rng.uniform(0.10, 0.17) / max(rate, 0.3)
                out = dsp.concat(out, self._syllable(f0, dur, rng, wi, s, syl, female))
            out = dsp.concat(out, dsp.silence(rng.uniform(0.03, 0.09) / max(rate, 0.3)))
            if word.endswith((",", "—", ":")):
                out = dsp.concat(out, dsp.silence(0.14 / max(rate, 0.3)))
            if word.endswith((".", "!", "?")):
                out = dsp.concat(out, dsp.silence(0.22 / max(rate, 0.3)))
        return dsp.normalize(out, -20.0, -3.0)

    def _syllable(self, f0, dur, rng, wi, si, syl, female):
        n = int(dur * SR)
        sig = dsp.new_signal(n)
        f1, f2 = self.VOWELS[rng.randrange(len(self.VOWELS))]
        if female:
            f1 *= 1.15
            f2 *= 1.1
        contour = 1.0 + 0.06 * math.sin(math.pi * si / max(1, syl)) - 0.02 * wi * 0.1
        phase = 0.0
        for i in range(n):
            t = i / SR
            freq = f0 * contour * (1.0 + 0.012 * math.sin(2 * math.pi * 4.7 * t))
            phase += 2 * math.pi * freq / SR
            # голосовой источник: пила с мягким спадом гармоник
            v = 0.0
            for h in range(1, 22):
                v += math.sin(phase * h) / (h ** 1.25)
            env = math.sin(math.pi * min(1.0, i / n)) ** 0.6
            sig[i] = v * 0.08 * env
        sig = dsp.chain(sig,
                        dsp.peaking(f1, 4.0, 12.0),
                        dsp.peaking(f2, 5.0, 10.0),
                        dsp.peaking(2700, 3.0, 5.0),
                        dsp.lowpass(6500, 0.7))
        return sig


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------

def _pitch_shift(sig: Signal, semitones: float) -> Signal:
    """Сдвиг высоты с сохранением длительности (varispeed + ресемплинг)."""
    factor = 2 ** (semitones / 12.0)
    fast = dsp.varispeed(sig, factor)
    return dsp.resample(fast, int(SR / factor), SR)


def _time_stretch_via_varispeed(sig: Signal, rate: float) -> Signal:
    """Изменение темпа с компенсацией высоты."""
    stretched = dsp.varispeed(sig, rate)
    return _pitch_shift(stretched, -12.0 * math.log2(rate))


def decode_audio(path: str) -> Signal:
    """Декодирует mp3/wav. Для mp3 используем ffmpeg, если он есть, иначе miniaudio/pydub."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        return dsp.read_wav(path)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        out.close()
        try:
            subprocess.run([ffmpeg, "-y", "-i", path, "-ar", str(SR), "-ac", "1", out.name],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return dsp.read_wav(out.name)
        finally:
            try:
                os.unlink(out.name)
            except OSError:
                pass

    # Чистый Python-декодер MP3 (без ffmpeg)
    try:
        import miniaudio  # type: ignore
        decoded = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.FLOAT32,
                                        nchannels=1, sample_rate=SR)
        return dsp.from_iter(decoded.samples)
    except Exception:
        pass
    try:
        from pydub import AudioSegment  # type: ignore
        seg = AudioSegment.from_file(path).set_channels(1).set_frame_rate(SR)
        scale = float(1 << (8 * seg.sample_width - 1))
        return dsp.from_iter(s / scale for s in seg.get_array_of_samples())
    except Exception as ex:
        raise TTSError(
            "Не удалось декодировать MP3. Установите ffmpeg, либо "
            "`pip install miniaudio` (чистый Python-декодер)."
        ) from ex


BACKEND_ORDER = ("edge", "piper", "silero", "espeak", "stub")

_REGISTRY = {
    "edge": EdgeBackend,
    "piper": PiperBackend,
    "silero": SileroBackend,
    "espeak": EspeakBackend,
    "stub": StubBackend,
}


def select_backend(preferred: str = "auto", verbose: bool = True) -> Backend:
    """Выбрать бэкенд: конкретный по имени или первый доступный из списка."""
    if preferred and preferred != "auto":
        cls = _REGISTRY.get(preferred)
        if cls is None:
            raise TTSError(f"Неизвестный TTS-бэкенд: {preferred}")
        b = cls()
        if not b.available() and preferred != "stub":
            raise TTSError(f"Бэкенд '{preferred}' недоступен в этой системе")
        return b

    for name in BACKEND_ORDER:
        b = _REGISTRY[name]()
        try:
            ok = b.available()
        except Exception:
            ok = False
        if ok:
            if verbose:
                print(f"[TTS] Выбран бэкенд: {b.name}")
            if b.name == "stub" and verbose:
                print("[TTS] ВНИМАНИЕ: доступен только процедурный стенд — "
                      "речь будет нечленораздельной. Это режим проверки пайплайна.")
            return b
    return StubBackend()
