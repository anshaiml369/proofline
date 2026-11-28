"""Run: python3 -m unittest discover tests"""
import unittest

import conversation as c
from hinglish_numbers import parse_amounts, parse_yes_no, to_words
from wage_math import calculate_wages, format_inr, payment_request


class WageMath(unittest.TestCase):
    def test_demo_case(self):
        r = calculate_wages(6, 700, 500, 3000)
        self.assertEqual((r["expected"], r["received"], r["outstanding"]), (4200, 3500, 700))

    def test_never_negative(self):
        r = calculate_wages(2, 500, 1000, 500)
        self.assertEqual((r["outstanding"], r["overpaid"]), (0, 500))

    def test_none_advance(self):
        self.assertEqual(calculate_wages(5, 600, None, None)["outstanding"], 3000)

    def test_rejects_bad_input(self):
        for bad in [(-1, 700, 0, 0), (6, "700", 0, 0), (6, 700.5, 0, 0), (True, 700, 0, 0)]:
            with self.assertRaises((TypeError, ValueError)):
                calculate_wages(*bad)

    def test_inr(self):
        self.assertEqual(format_inr(4200), "₹4,200")
        self.assertEqual(format_inr(125000), "₹1,25,000")
        self.assertEqual(format_inr(700), "₹700")

    def test_message_uses_python_numbers(self):
        msg = payment_request(calculate_wages(6, 700, 500, 3000))
        for s in ["6 din × ₹700 = ₹4,200", "₹500", "₹3,000", "₹3,500", "Baaki: ₹700"]:
            self.assertIn(s, msg)


class Numbers(unittest.TestCase):
    def test_words(self):
        self.assertEqual(to_words(4200), "chaar hazaar do sau")
        self.assertEqual(to_words(3500), "teen hazaar paanch sau")
        self.assertEqual(to_words(700), "saat sau")
        self.assertEqual(to_words(6), "chhe")
        self.assertEqual(to_words(125000), "ek lakh pachchees hazaar")

    def test_parse(self):
        cases = {"Chhe din.": [6], "Saat sau rupaye.": [700], "Teen hazaar.": [3000], "Paanch sau.": [500],
                 "chaar hazaar do sau": [4200], "₹3,000": [3000], "3000 rupaye": [3000], "छह दिन": [6],
                 "तीन हज़ार": [3000], "dedh hazaar": [1500], "saadhe teen hazaar": [3500], "2k": [2000],
                 "do hazaar aur ek hazaar": [2000, 1000], "pata nahi": []}
        for text, want in cases.items():
            self.assertEqual(parse_amounts(text), want, text)

    def test_yes_no(self):
        self.assertIs(parse_yes_no("Haan."), True)
        self.assertIs(parse_yes_no("haan bhej do"), True)
        self.assertIs(parse_yes_no("sahi nahi hai"), False)
        self.assertIs(parse_yes_no("हाँ"), True)
        self.assertIsNone(parse_yes_no("hmm"))


def run(lines, extract=c.local_extract):
    s = c.new_session()
    c.opening(s)
    out = []
    for line in lines:
        out.append(c.step(s, line, extract))
    return s, out


DEMO = ["Mujhe thekedar ne is hafte poore paise nahi diye.", "Chhe din.", "Saat sau rupaye.",
        "Paanch sau.", "Teen hazaar.", "Haan.", "Haan."]


class Conversation(unittest.TestCase):
    def test_demo(self):
        s, out = run(DEMO)
        texts = [o["agent_text"] for o in out]
        self.assertEqual(texts[0], "Aapne kitne din kaam kiya?")
        self.assertEqual(texts[4], "Confirm karta hoon: chhe din, saat sau roz, paanch sau advance, "
                                   "teen hazaar paid. Sahi hai?")
        self.assertEqual(texts[5], "Kul kamaai chaar hazaar do sau. Mila teen hazaar paanch sau. "
                                   "Baaki saat sau rupaye. Thekedar ko payment request bhejun?")
        self.assertEqual(s["case"]["outstanding"], 700)
        self.assertEqual(out[-1]["state"], c.SEND_BUTTON)
        self.assertIn("Baaki: ₹700", out[-1]["case"]["payment_request"])
        c.step(s, "haan", c.local_extract)       # talking does not send
        self.assertEqual(s["state"], c.SEND_BUTTON)
        self.assertEqual(c.mark_sent(s)["state"], c.DONE)
        self.assertIsNone(c.mark_sent(s))

    def test_confirm_is_mandatory(self):
        s, out = run(DEMO[:5])
        self.assertEqual(s["state"], c.CONFIRM)
        self.assertIsNone(s["case"])           # nothing calculated before "haan"
        out2 = c.step(s, "hmm", c.local_extract)
        self.assertIsNone(s["case"])
        self.assertEqual(s["state"], c.CONFIRM)
        self.assertTrue(out2["reasked"])

    def test_confirm_no_restarts(self):
        s, out = run(DEMO[:5] + ["Nahi, galat hai"])
        self.assertEqual(s["state"], c.ASK_DAYS)
        self.assertEqual(s["facts"], {})

    def test_low_confidence_reasks_once_then_text(self):
        s, out = run(["shikayat", "pata nahi"])
        self.assertEqual(s["state"], c.ASK_DAYS)
        self.assertEqual(out[1]["agent_text"], c.QUESTIONS[c.ASK_DAYS][2])
        self.assertFalse(out[1]["fallback_text"])
        third = c.step(s, "kuch yaad nahi", c.local_extract)
        self.assertTrue(third["fallback_text"])
        fourth = c.step(s, "6", c.local_extract)
        self.assertEqual(s["state"], c.ASK_RATE)

    def test_llm_low_confidence_is_reasked(self):
        low = lambda f, q, t: {"field": f, "value": 700, "confidence": "low"}
        s, out = run(["x", "saat"], extract=low)
        self.assertEqual(s["state"], c.ASK_DAYS)
        self.assertTrue(out[1]["reasked"])

    def test_llm_cannot_sneak_arithmetic(self):
        # LLM returns parts; Python sums them.
        def ex(f, q, t):
            if f == "payments":
                return {"field": f, "value": None, "parts": [2000, 1000], "confidence": "high"}
            return c.local_extract(f, q, t)
        s, _ = run(["x", "6", "700", "500", "do hazaar aur ek hazaar", "haan"], extract=ex)
        self.assertEqual(s["case"]["payments"], 3000)
        self.assertEqual(s["case"]["outstanding"], 700)

    def test_nothing_due(self):
        s, out = run(["x", "4", "500", "nahi", "do hazaar", "haan"])
        self.assertEqual(s["case"]["outstanding"], 0)
        self.assertIn("koi paisa baaki nahi", out[-1]["agent_text"])
        self.assertTrue(out[-1]["done"])
        self.assertNotIn("payment_request", s["case"])

    def test_implausible_value_reasked(self):
        s, out = run(["x", "500"])  # 500 days
        self.assertEqual(s["state"], c.ASK_DAYS)


if __name__ == "__main__":
    unittest.main()
