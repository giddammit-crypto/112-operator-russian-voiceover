"""
Тесты конвейера озвучки. Запуск:  python3 -m tests.test_voicepack
(или: python3 -m unittest discover -s tests)

Тесты не требуют сети, ffmpeg и установленной игры: TTS работает через
процедурный стенд, а данные игры подменяются временным фикстуром.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voicepack import dsp, fx  # noqa: E402
from voicepack.build_calls import load_localization, parse_calls  # noqa: E402
from voicepack.casting import RADIO_CAST, alt_of, caller_profile  # noqa: E402
from voicepack.emotions import from_text, from_xml_tag, get  # noqa: E402
from voicepack.render import render_hangup, render_line  # noqa: E402
from voicepack.scripts_radio import ALIASES, CHATTER, SCRIPTS  # noqa: E402
from voicepack.text_norm import (normalize_for_speech, number_to_words,  # noqa: E402
                                 split_screen_tag)
from voicepack.tts import StubBackend  # noqa: E402


# ---------------------------------------------------------------------------
# Фикстура «установленной игры»
# ---------------------------------------------------------------------------

CALL_XML = """<?xml version="1.0" encoding="utf-8"?>
<call>
  <incident id="c_test_crash" properties="sex=FEMALE">
    <dialogOption id="1" operator="operator" texten="What happened?" />
    <dialogOption id="2" emotions="panic,crying" texten="Car crash!" />
    <dialogOption id="3" operator="operator" texten="Stay calm" />
    <dialogOption id="4" emotions="pain" texten="My leg" />
    <dialogOption id="5_hangup" texten="" />
  </incident>
</call>
"""

RU_TXT = """{
    "incident.c_test_crash.dialog.1": "{ЧТО СЛУЧИЛОСЬ?} Служба 112, что у вас произошло?",
    "incident.c_test_crash.dialog.2": "Авария!!! Машина перевернулась на ул. Ленина, д. 12!",
    "incident.c_test_crash.dialog.3": "Сохраняйте спокойствие, бригада уже выехала.",
    "incident.c_test_crash.dialog.4": "Нога... я не могу пошевелить ногой... больно...",
    "incident.c_test_crash.dialog.5_hangup": "",
    "text.other.ignored": "не диалог"
}
"""


def make_fixture(root: str) -> str:
    sa = os.path.join(root, "Operator 112_Data", "StreamingAssets")
    os.makedirs(os.path.join(sa, "Languages"), exist_ok=True)
    os.makedirs(os.path.join(sa, "Calls"), exist_ok=True)
    with open(os.path.join(sa, "Languages", "ru-RU.txt"), "w", encoding="utf-8") as f:
        f.write(RU_TXT)
    with open(os.path.join(sa, "Calls", "c_test_crash.xml"), "w", encoding="utf-8") as f:
        f.write(CALL_XML)
    return sa


# ---------------------------------------------------------------------------

class TestTextNorm(unittest.TestCase):

    def test_numbers(self):
        self.assertEqual(number_to_words(0), "ноль")
        self.assertEqual(number_to_words(12), "двенадцать")
        self.assertEqual(number_to_words(45), "сорок пять")
        self.assertEqual(number_to_words(112), "сто двенадцать")
        self.assertEqual(number_to_words(1000), "одна тысяча")
        self.assertEqual(number_to_words(2345),
                         "две тысячи триста сорок пять")

    def test_emergency_number(self):
        self.assertIn("сто двенадцать", normalize_for_speech("Звоните в 112"))

    def test_screen_tag_split(self):
        tag, spoken = split_screen_tag("{ЧТО СЛУЧИЛОСЬ?} Что у вас произошло?")
        self.assertEqual(tag, "ЧТО СЛУЧИЛОСЬ?")
        self.assertEqual(spoken, "Что у вас произошло?")

    def test_screen_tag_only(self):
        tag, spoken = split_screen_tag("{ПОНЯТНО}")
        self.assertEqual(spoken, "ПОНЯТНО")

    def test_no_latin_left(self):
        out = normalize_for_speech("Вызов OK, ждите police")
        self.assertNotRegex(out, r"[A-Za-z]")

    def test_abbreviations_cases(self):
        out = normalize_for_speech("Авария на ул. Ленина, д. 5")
        self.assertIn("на улице Ленина", out)
        self.assertIn("дом пять", out)

    def test_markup_stripped(self):
        out = normalize_for_speech("[[0.5]]Он <b>не дышит</b> (плачет)")
        self.assertNotIn("[[", out)
        self.assertNotIn("<b>", out)
        self.assertNotIn("(", out)

    def test_acronyms(self):
        self.assertIn("дэ-тэ-пэ", normalize_for_speech("Оформляем ДТП"))


class TestEmotions(unittest.TestCase):

    def test_xml_mapping(self):
        self.assertEqual(from_xml_tag("panic,crying"), "panic")
        self.assertEqual(from_xml_tag("in_pain"), "pain")
        self.assertEqual(from_xml_tag(""), "neutral")
        self.assertEqual(from_xml_tag("something_unknown"), "neutral")

    def test_text_heuristics(self):
        self.assertEqual(from_text("ПОМОГИТЕ НАМ СРОЧНО"), "shout")
        self.assertEqual(from_text("Помогите! Тут стреляют!"), "panic")
        self.assertEqual(from_text("Мне очень больно, нога"), "pain")

    def test_every_emotion_resolves(self):
        for cat in SCRIPTS.values():
            for lines in cat.values():
                for _text, emotion in lines:
                    self.assertEqual(get(emotion).key, emotion,
                                     f"Неизвестная эмоция: {emotion}")
        for _t, emotion in CHATTER:
            self.assertEqual(get(emotion).key, emotion)


class TestDSP(unittest.TestCase):

    def test_limiter_respects_ceiling(self):
        import random
        rng = random.Random(0)
        sig = dsp.from_iter(rng.uniform(-3, 3) for _ in range(20000))
        out = dsp.limiter(sig, ceiling_db=-1.0)
        self.assertLessEqual(dsp.peak(out), dsp.db_to_lin(-1.0) + 1e-3)

    def test_normalize_targets_rms(self):
        import random
        rng = random.Random(1)
        sig = dsp.from_iter(rng.uniform(-0.01, 0.01) for _ in range(44100))
        out = dsp.normalize(sig, -18.0, -1.0)
        self.assertAlmostEqual(dsp.lin_to_db(dsp.rms(out)), -18.0, delta=1.0)

    def test_bandpass_attenuates_out_of_band(self):
        import math
        n = 44100
        low = dsp.from_iter(math.sin(2 * math.pi * 80 * i / dsp.SR) for i in range(n))
        mid = dsp.from_iter(math.sin(2 * math.pi * 1200 * i / dsp.SR) for i in range(n))
        low_f = dsp.steep_bandpass(low, 400, 3400, 3)
        mid_f = dsp.steep_bandpass(mid, 400, 3400, 3)
        self.assertLess(dsp.rms(low_f), dsp.rms(mid_f) * 0.05)

    def test_wav_roundtrip(self):
        import random
        rng = random.Random(2)
        sig = dsp.from_iter(rng.uniform(-0.5, 0.5) for _ in range(4410))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.wav")
            dsp.write_wav(p, sig)
            with wave.open(p, "rb") as w:
                self.assertEqual(w.getframerate(), 44100)
                self.assertEqual(w.getsampwidth(), 2)
                self.assertEqual(w.getnchannels(), 2)
            back = dsp.read_wav(p)
            self.assertEqual(len(back), len(sig))
            for a, b in zip(sig, back):
                self.assertLess(abs(a - b), 1e-3)

    def test_varispeed_changes_length(self):
        sig = dsp.silence(1.0)
        self.assertAlmostEqual(dsp.duration(dsp.varispeed(sig, 2.0)), 0.5, delta=0.01)

    def test_trim_silence(self):
        sig = dsp.concat(dsp.silence(0.5), dsp.from_iter([0.5] * 4410), dsp.silence(0.5))
        trimmed = dsp.trim_silence(sig)
        self.assertLess(dsp.duration(trimmed), 0.3)


class TestFX(unittest.TestCase):

    def test_ptt_elements_nonempty(self):
        import random
        rng = random.Random(0)
        for sig in (fx.ptt_press(rng), fx.ptt_release(rng), fx.roger_beep(rng)):
            self.assertGreater(len(sig), 100)
            self.assertGreater(dsp.peak(sig), 0.01)
            self.assertLessEqual(dsp.peak(sig), 1.0)


class TestCasting(unittest.TestCase):

    def test_roles_distinct(self):
        keys = {r.varispeed for r in RADIO_CAST.values()}
        self.assertGreaterEqual(len(keys), 4, "Роли должны звучать по-разному")

    def test_alt_actor_differs(self):
        for key in ("Male1", "Male2", "Female1", "Female2"):
            self.assertNotEqual(RADIO_CAST[key].varispeed, alt_of(key).varispeed)

    def test_caller_pool_stable_and_varied(self):
        a = caller_profile("FEMALE", 3)
        b = caller_profile("FEMALE", 3)
        self.assertEqual(a.key, b.key, "Один вызов — один голос")
        seen = {caller_profile("MALE", i).key for i in range(4)}
        self.assertGreaterEqual(len(seen), 3, "Звонящие должны различаться")

    def test_phone_line_applied(self):
        p = caller_profile("MALE", 0)
        self.assertLessEqual(p.band_high, 3400.0)


class TestScripts(unittest.TestCase):

    def test_all_roles_present(self):
        for cat, roles in SCRIPTS.items():
            self.assertTrue(roles, f"Пустая категория {cat}")
            for role, lines in roles.items():
                self.assertIn(role, ("Male1", "Male2", "Female1", "Female2"))
                for text, emotion in lines:
                    self.assertTrue(text.strip(), f"Пустая реплика в {cat}/{role}")
                    self.assertIsInstance(emotion, str)

    def test_no_latin_in_scripts(self):
        for cat, roles in SCRIPTS.items():
            for role, lines in roles.items():
                for text, _e in lines:
                    self.assertNotRegex(text, r"[A-Za-z]",
                                        f"Латиница в реплике {cat}/{role}: {text}")

    def test_aliases_cover_categories(self):
        for cat in SCRIPTS:
            self.assertIn(cat, ALIASES, f"Нет раскладки алиасов для {cat}")

    def test_chatter_nonempty(self):
        self.assertGreaterEqual(len(CHATTER), 15)


class TestRender(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tts = StubBackend()
        cls.raw = cls.tts.synth("Центр, экипаж на месте, обстановка спокойная.",
                                "ru-RU-DmitryNeural", 1.0, 0.0)

    def test_radio_clip_valid(self):
        clip = render_line(self.raw, RADIO_CAST["Male1"], "calm", 1, mode="radio")
        self.assertGreater(dsp.duration(clip), 0.5)
        self.assertLessEqual(dsp.peak(clip), 1.0)
        self.assertGreater(dsp.rms(clip), 0.0)

    def test_all_modes_render(self):
        for mode in ("radio", "chatter", "phone", "headset"):
            clip = render_line(self.raw, RADIO_CAST["Male1"], "urgent", 7, mode=mode)
            self.assertGreater(len(clip), 1000, f"Пустой клип в режиме {mode}")
            self.assertLessEqual(dsp.peak(clip), 1.0)

    def test_emotion_changes_result(self):
        calm = render_line(self.raw, RADIO_CAST["Male2"], "calm", 5, mode="radio")
        combat = render_line(self.raw, RADIO_CAST["Male2"], "combat", 5, mode="radio")
        self.assertNotEqual(len(calm), len(combat))

    def test_deterministic(self):
        a = render_line(self.raw, RADIO_CAST["Female1"], "urgent", 42, mode="radio")
        b = render_line(self.raw, RADIO_CAST["Female1"], "urgent", 42, mode="radio")
        self.assertEqual(list(a), list(b), "Рендер должен быть воспроизводимым")

    def test_hangup_tone(self):
        clip = render_hangup(0)
        self.assertGreater(dsp.duration(clip), 1.0)


class TestCallsParsing(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sa = make_fixture(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_localization(self):
        texts = load_localization(os.path.join(self.sa, "Languages", "ru-RU.txt"))
        self.assertEqual(len(texts), 5)
        self.assertIn("incident.c_test_crash.dialog.2", texts)
        self.assertNotIn("text.other.ignored", texts)

    def test_call_metadata(self):
        calls = parse_calls(self.sa)
        self.assertIn("c_test_crash", calls)
        meta = calls["c_test_crash"]
        self.assertEqual(meta["sex"], "FEMALE")
        self.assertEqual(len(meta["options"]), 5)
        self.assertTrue(meta["options"]["1"]["is_operator"])
        self.assertFalse(meta["options"]["2"]["is_operator"])
        self.assertEqual(meta["ambience"], "car")


class TestEndToEnd(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sa = make_fixture(self.tmp)
        self.out = os.path.join(self.tmp, "out")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_calls(self):
        from voicepack.build_calls import build_calls
        m = build_calls(self.out, "stub", self.sa, jobs=1, progress=lambda *a: None)
        self.assertEqual(m["count"], 5)

        d = os.path.join(self.out, "RussianCalls", "c_test_crash")
        for opt in ("1", "2", "3", "4", "5_hangup"):
            p = os.path.join(d, f"{opt}.wav")
            self.assertTrue(os.path.exists(p), f"Нет файла {opt}.wav")
            with wave.open(p, "rb") as w:
                self.assertEqual(w.getframerate(), 44100)
                self.assertEqual(w.getnchannels(), 2)

        by_opt = {e["option"]: e for e in m["entries"]}
        self.assertEqual(by_opt["1"]["kind"], "operator")
        self.assertEqual(by_opt["2"]["kind"], "caller")
        self.assertEqual(by_opt["2"]["emotion"], "panic")
        self.assertEqual(by_opt["4"]["emotion"], "pain")
        self.assertEqual(by_opt["5_hangup"]["kind"], "hangup")
        # Оператор не должен произносить экранный тег
        self.assertNotIn("ЧТО СЛУЧИЛОСЬ", by_opt["1"]["text"])

    def test_build_radio_subset(self):
        from voicepack.build_radio import build_radio
        m = build_radio(self.out, "stub", only_category="roger", jobs=1,
                        progress=lambda *a: None)
        self.assertGreater(m["count"], 0)
        for role in ("Male1", "Male2", "Female1", "Female2"):
            d = os.path.join(self.out, "RussianRadio", role)
            self.assertTrue(os.path.isdir(d))
            self.assertTrue([f for f in os.listdir(d) if f.startswith("roger_")])

    def test_verify_passes(self):
        from voicepack.build_radio import build_radio
        from voicepack.verify import verify_pack
        build_radio(self.out, "stub", only_category="roger", jobs=1,
                    progress=lambda *a: None)
        with open(os.path.join(self.out, "russian_radio_manifest.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"count": 1, "backend": "stub"}, f)
        self.assertTrue(verify_pack(self.out))

    def test_install_layout(self):
        from voicepack.build_radio import build_radio
        from voicepack.install import copy_audio
        build_radio(self.out, "stub", only_category="roger", jobs=1,
                    progress=lambda *a: None)
        n = copy_audio(self.out, self.tmp)
        self.assertGreater(n, 0)
        target = os.path.join(self.tmp, "Operator 112_Data", "StreamingAssets",
                              "Audio", "RussianRadio", "Male1")
        self.assertTrue(os.path.isdir(target))


if __name__ == "__main__":
    unittest.main(verbosity=2)
