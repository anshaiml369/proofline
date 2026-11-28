"""The state machine, driven with the built-in rules (no API keys)."""
import pytest

import conversation as c
from hinglish_numbers import parse_amounts, parse_yes_no, to_words

DEMO = ["Mujhe thekedar ne is hafte poore paise nahi diye.", "Chhe din.", "Saat sau rupaye.",
        "Paanch sau.", "Teen hazaar.", "Haan.", "Haan."]


def run(lines, extract=c.local_extract):
    s = c.new_session()
    c.opening(s)
    return s, [c.step(s, line, extract) for line in lines]


def test_demo_flow():
    s, out = run(DEMO)
    assert out[0]["agent_text"] == "Aapne kitne din kaam kiya?"
    assert out[4]["agent_text"] == ("Confirm karta hoon: chhe din, saat sau roz, paanch sau advance, "
                                    "teen hazaar paid. Sahi hai?")
    assert out[5]["agent_text"] == ("Kul kamaai chaar hazaar do sau. Mila teen hazaar paanch sau. "
                                    "Baaki saat sau rupaye. Thekedar ko payment request bhejun?")
    assert out[5]["speak_text"] == "कुल कमाई 4200 रुपये। मिला 3500 रुपये। बाकी 700 रुपये। ठेकेदार को पेमेंट रिक्वेस्ट भेजूँ?"
    assert s["case"]["outstanding"] == 700
    assert out[-1]["state"] == c.SHOW_PREVIEW
    assert "Baaki: ₹700" in s["case"]["payment_request"]


def test_wispr_style_text():
    # Wispr Flow may write digits, rupee signs or Devanagari instead of words
    s, _ = run(["paise nahi mile", "6 din", "₹700", "500 rupaye", "3,000", "हाँ"])
    assert s["case"]["outstanding"] == 700


def test_send_needs_the_button():
    s, _ = run(DEMO)
    c.step(s, "haan", c.local_extract)
    assert s["state"] == c.SHOW_PREVIEW
    assert c.mark_sent(s)["state"] == c.DONE
    assert c.mark_sent(s) is None


def test_confirm_is_mandatory():
    s, _ = run(DEMO[:5])
    assert s["state"] == c.CONFIRM and s["case"] is None
    out = c.step(s, "hmm", c.local_extract)
    assert out["reasked"] and s["case"] is None and s["state"] == c.CONFIRM


def test_confirm_no_goes_back_to_days():
    s, _ = run(DEMO[:5] + ["Nahi, galat hai"])
    assert s["state"] == c.ASK_DAYS and s["facts"] == {}


def test_reask_once_then_needs_assistance():
    s, out = run(["x", "pata nahi"])
    assert out[1]["agent_text"] == c.STATES[c.ASK_DAYS]["simpler"][0]
    assert not out[1]["needs_assistance"]
    third = c.step(s, "yaad nahi", c.local_extract)
    assert third["needs_assistance"] and s["state"] == c.ASK_DAYS   # days can't be guessed
    c.step(s, "6", c.local_extract)
    assert s["state"] == c.ASK_RATE


def test_unclear_advance_moves_on_as_zero_with_flag():
    s, out = run(["x", "6", "700", "hmm", "pata nahi"])
    assert s["state"] == c.ASK_PAYMENTS
    assert s["facts"]["advance"] == 0 and out[-1]["needs_assistance"]


def test_parts_are_added_in_python():
    def ex(f, q, t):
        if f == "payments":
            return {"field": f, "value": None, "parts": [2000, 1000], "confidence": "high"}
        return c.local_extract(f, q, t)
    s, _ = run(["x", "6", "700", "500", "do hazaar aur ek hazaar", "haan"], extract=ex)
    assert s["case"]["payments"] == 3000 and s["case"]["outstanding"] == 700


def test_nothing_due():
    s, out = run(["x", "5", "800", "nahi", "chaar hazaar", "haan"])
    assert s["case"]["outstanding"] == 0
    assert "koi paisa baaki nahi" in out[-1]["agent_text"]
    assert out[-1]["done"] and "payment_request" not in s["case"]


def test_implausible_value_reasked():
    s, _ = run(["x", "500"])          # 500 days
    assert s["state"] == c.ASK_DAYS


@pytest.mark.parametrize("text, want", [
    ("Chhe din.", [6]), ("Saat sau rupaye.", [700]), ("Teen hazaar.", [3000]), ("chaar hazaar do sau", [4200]),
    ("₹3,000", [3000]), ("छह दिन", [6]), ("तीन हज़ार", [3000]), ("dedh hazaar", [1500]),
    ("saadhe teen hazaar", [3500]), ("2k", [2000]), ("do hazaar aur ek hazaar", [2000, 1000]), ("pata nahi", []),
])
def test_parse_amounts(text, want):
    assert parse_amounts(text) == want


def test_dont_know_is_not_zero():
    from hinglish_numbers import says_none
    assert says_none("nahi mila") and says_none("kuch nahi")
    assert not says_none("pata nahi") and not says_none("yaad nahi")


def test_words_and_yes_no():
    assert to_words(4200) == "chaar hazaar do sau"
    assert parse_yes_no("haan bhej do") is True
    assert parse_yes_no("sahi nahi hai") is False
    assert parse_yes_no("हाँ") is True
