"""Builds test_cases.json. Expected `outstanding` is computed by wage_math (Python), never typed by hand.
Written before running any version against it; see TEST_SET.md."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wage_math import calculate_wages  # noqa: E402


def case(id, cat, turns, d, r, a, p, notes, ctx=False, ctx_turn=None, ctx_kw=(), bundled_turn=None, bundled_slots=()):
    return {"id": id, "category": cat, "turns": turns,
            "expected": {"days": d, "rate": r, "advance": a, "payments": p,
                         "outstanding": calculate_wages(d, r, a, p)["outstanding"]},
            "expect_context_ack": bool(ctx), "context_turn": ctx_turn, "context_keywords": list(ctx_kw),
            "bundled_turn": bundled_turn, "bundled_slots": list(bundled_slots), "notes": notes}


ALL = ("days", "rate", "advance", "payments")
CASES = [
    case("A1", "A canonical", ["paise nahi mile", "chhe din", "saat sau rupaye", "paanch sau", "teen hazaar"],
         6, 700, 500, 3000, "The demo. Ends at ₹700."),
    case("A2", "A canonical", ["thekedar ne poore paise nahi diye", "das din", "paanch sau", "do sau", "teen hazaar"],
         10, 500, 200, 3000, "Required case (10, 500, 200, 3000) -> 1800."),
    case("B1", "B bundled", ["Chhe din kaam kiya, saat sau roz, paanch sau advance, teen hazaar mila"],
         6, 700, 500, 3000, "All four slots in the first message.", bundled_turn=0, bundled_slots=ALL),
    case("B2", "B bundled", ["paise baaki hain", "8 din kaam, 650 roz, advance 1000, 3000 mile"],
         8, 650, 1000, 3000, "All four slots in one answer to the days question.", bundled_turn=1, bundled_slots=ALL),
    case("C1", "C bundled+context",
         ["Teen saal se is kaam par hoon, pichhle hafte hospital tha, chhe din kaam kiya, saat sau roz, paanch sau advance, teen hazaar mila"],
         6, 700, 500, 3000, "Bundle plus tenure and hospital context.", ctx=True, ctx_turn=0,
         ctx_kw=("hospital", "saal", "dukh", "afsos", "bimar", "theek ho"), bundled_turn=0, bundled_slots=ALL),
    case("C2", "C bundled+context",
         ["Meri biwi bimar thi isliye 2 din chhutti li, baaki 5 din kaam kiya, 800 roz, advance nahi, 2000 mile"],
         5, 800, 0, 2000, "Bundle plus a family illness; the 2 leave days must not count.", ctx=True, ctx_turn=0,
         ctx_kw=("biwi", "patni", "bimar", "dukh", "afsos", "chhutti"), bundled_turn=0, bundled_slots=ALL),
    case("D1", "D vague", ["paise nahi mile", "pata nahi", "yaad nahi", "6 din", "700", "500", "3000"],
         6, 700, 500, 3000, "Two vague answers on days, then the number."),
    case("D2", "D vague", ["paise nahi mile", "6 din", "pata nahi kitna tha", "yaad nahi aa raha", "700", "500", "3000"],
         6, 700, 500, 3000, "Two vague answers on rate."),
    case("E1", "E refusal", ["paise nahi mile", "nahi bataunga", "achha theek hai, 6 din", "700 roz", "500 advance", "3000 mile"],
         6, 700, 500, 3000, "Refuses once, then cooperates."),
    case("E2", "E refusal", ["paise nahi mile", "5 din", "yeh sab kyun poochh rahe ho, nahi bataunga", "theek hai, 900 roz",
                             "advance nahi mila", "1000 mile"],
         5, 900, 0, 1000, "Refuses the rate once, then answers."),
    case("F1", "F off-topic", ["paise nahi mile", "6 din", "mera beta bimar hai", "700 roz", "500 advance", "3000 mile"],
         6, 700, 500, 3000, "Off-topic personal news mid-flow.", ctx=True, ctx_turn=2,
         ctx_kw=("beta", "bete", "bimar", "dukh", "afsos", "chinta")),
    case("F2", "F off-topic", ["paise nahi mile", "aaj baarish bahut ho rahi hai", "7 din", "600", "nahi", "2000"],
         7, 600, 0, 2000, "Weather small talk before the first answer.", ctx=True, ctx_turn=1,
         ctx_kw=("baarish", "barish", "mausam", "barsaat")),
    case("G1", "G contradiction", ["paise nahi mile", "6 din", "700", "500", "2000", "nahi, 5 din the"],
         5, 700, 500, 2000, "Corrects days at the read-back."),
    case("G2", "G contradiction", ["paise nahi mile", "6 din", "800 roz", "nahi nahi, 5 din kaam kiya tha", "advance nahi", "1000 mile"],
         5, 800, 0, 1000, "Corrects days while being asked about the advance."),
    case("H1", "H zero owed", ["paise ka hisaab dekhna hai", "5 din", "800", "advance nahi", "poora paisa mil gaya, 4000"],
         5, 800, 0, 4000, "Required case (5, 800, 0, 4000) -> 0."),
    case("H2", "H zero owed", ["bas confirm karna hai", "4 din", "500 roz", "500 advance", "1500 mile"],
         4, 500, 500, 1500, "Fully paid: ₹0 owed."),
    case("I1", "I loan vs advance", ["paise nahi mile", "30 din", "600 roz", "manager se paanch hazaar liya",
                                     "haan, pagar mein se kaat liya", "8000 mile"],
         30, 600, 5000, 8000, "A loan cut from wages is advance.", ctx=True, ctx_turn=3,
         ctx_kw=("loan", "kaat", "kata", "udhaar", "manager", "mazdoori se")),
    case("I2", "I loan vs advance", ["paise nahi mile", "10 din", "700",
                                     "dost se 2000 udhaar liya tha, woh alag hai, advance nahi mila", "4000 mile"],
         10, 700, 0, 4000, "A private loan is NOT advance.", ctx=True, ctx_turn=3,
         ctx_kw=("udhaar", "loan", "dost", "alag")),
    case("J1", "J Hindi words", ["paise nahi mile", "chhe", "saat sau", "paanch sau", "teen hazaar"],
         6, 700, 500, 3000, "Roman Hindi number words."),
    case("J2", "J Hindi words", ["पैसे नहीं मिले", "छह दिन", "सात सौ", "पाँच सौ", "तीन हज़ार"],
         6, 700, 500, 3000, "Devanagari number words."),
    case("K1", "K digits", ["paise nahi mile", "6 din", "700 rate", "₹500", "₹3,000"],
         6, 700, 500, 3000, "Digits and ₹ signs."),
    case("K2", "K digits", ["paise nahi mile", "12", "550", "0", "4,000"],
         12, 550, 0, 4000, "Bare digits, a 0 advance, comma thousands."),
    case("L1", "L code-mix", ["My contractor did not pay me", "I worked 6 days, rate 700", "advance 500", "received 3000"],
         6, 700, 500, 3000, "English code-mix, two facts in one answer.", bundled_turn=1, bundled_slots=("days", "rate")),
    case("L2", "L code-mix", ["payment pending hai", "worked 9 days", "daily 750", "no advance", "got 5000 so far"],
         9, 750, 0, 5000, "Hinglish with English phrasing."),
    case("M1", "M long multi-fact",
         ["Dekho bhai, Somvaar se Shanivaar tak chhe din kaam kiya site pe, thekedar ne saat sau roz bola tha, "
          "shuru mein paanch sau advance diya aur kal teen hazaar diye, baaki nahi diya"],
         6, 700, 500, 3000, "One long sentence with all four facts.", bundled_turn=0, bundled_slots=ALL),
    case("M2", "M long multi-fact",
         ["paise nahi mile", "humne pichhle mahine 20 din kaam kiya tha aur 600 roz pe baat hui thi, "
          "beech mein 2000 advance liya aur abhi 6000 mile hain"],
         20, 600, 2000, 6000, "A long answer to the days question with all four facts.", bundled_turn=1, bundled_slots=ALL),
    case("N1", "N skip ahead", ["paise nahi mile", "700 roz milta tha", "6 din", "500 advance", "3000 mile"],
         6, 700, 500, 3000, "Gives the rate when asked for days."),
    case("N2", "N skip ahead", ["paise nahi mile", "3000 mile hain bas", "6 din", "700", "500 advance"],
         6, 700, 500, 3000, "Gives payments first."),
    case("O1", "O correction", ["paise nahi mile", "6 din", "700", "nahi nahi, roz 800 tha", "500 advance", "3000 mile"],
         6, 800, 500, 3000, "Corrects the rate mid-stream."),
    case("O2", "O correction", ["paise nahi mile", "6 din", "700", "1000 advance", "sorry, advance 500 tha", "3000 mile"],
         6, 700, 500, 3000, "Corrects the advance mid-stream."),
    case("P1", "P silence", ["...", "hmm", "6 din", "700", "500", "3000"],
         6, 700, 500, 3000, "Near-silent dictation (dots, a hum)."),
    case("P2", "P silence", ["paise nahi mile", "6 din", "...", "700", "500", "3000"],
         6, 700, 500, 3000, "Silence after the rate question."),
]

if __name__ == "__main__":
    out = os.path.join(ROOT, "test_cases.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(CASES, f, ensure_ascii=False, indent=1)
    print(len(CASES), "cases ->", out)
