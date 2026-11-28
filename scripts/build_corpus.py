"""Writes test_corpus.json: 115 scripted conversations in classes A-H (see TEST_CORPUS.md).

The brief asked for "100 conversations" and for 15 per class A, B, C, D, F, G, H plus 10 for E; those
counts add up to 115, so the per-class counts are kept and the total is 115.

    python3 scripts/build_corpus.py

Expected numbers are what a careful human would write down from the worker's words, using the stated
assumptions (26 working days a month, 4.33 weeks a month, 6 days a week when nothing else is said).
They are not read from the agent's output.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = []


def case(cid, cls, turns, days, rate, advance=0, payments=0, deductions=0, bonus=0, must=(), notes="",
         hard=False, scripted_confirm=False):
    expected = days * rate + bonus - deductions
    canonical = {"days": days, "rate": rate, "advance": advance, "payments": payments}
    if deductions:
        canonical["deductions"] = deductions
    if bonus:
        canonical["bonus"] = bonus
    CASES.append({"id": cid, "class": cls, "turns": list(turns), "expected_canonical": canonical,
                  "expected_outstanding": max(0, expected - advance - payments),
                  "must_contain_in_agent": list(must), "must_not_repeat": True,
                  "must_pass_hard": hard, "scripted_confirm": scripted_confirm, "notes": notes})


A, B, C, D, E, F, G, H = ("A period-not-daycount", "B rate-period", "C deductions/non-cash", "D advance-ambiguity",
                          "E context/emotion", "F corrections", "G format", "H dispute/legal")

# ---------- A: the worker gives a period, not a day count ----------
case("A1", A, ["meri pagar badhao.", "kuch 5-6 mahine", "maine kareeb har hafte ke paanch din",
               "Hafte mein 7 din mein se 5 din kaam kiye. 5 din", "roz 700", "advance nahi mila",
               "nabbe hazaar teen sau mile"],
     130, 700, 0, 90300, must=["130", "5-6 mahine, hafte mein 5 din"], hard=True, scripted_confirm=True,
     notes="The proof conversation. 5-6 months x 4.33 x 5 = 130 days, 130 x 700 = 91000, 91000 - 90300 = 700.")
case("A2", A, ["paise nahi mile", "teen hafte kaam kiya", "roz 600", "advance nahi", "5000 mile"],
     18, 600, 0, 5000, must=["18"], notes="3 weeks, no frequency: 6 days/week assumed and said.")
case("A3", A, ["hisaab chahiye", "teen hafte, hafte mein 6 din", "700 roz", "nahi", "10000"],
     18, 700, 0, 10000, must=["18"], notes="3 weeks x 6 days/week.")
case("A4", A, ["paise baaki hain", "aadha mahina", "500 roz", "advance nahi liya", "4000 mile"],
     13, 500, 0, 4000, must=["13"], notes="Half a month x 26 = 13.")
case("A5", A, ["thekedar ne paise nahi diye", "pichhle mahine se", "nahi, ek mahina", "roz 500", "1000 advance",
               "8000 mile"],
     26, 500, 1000, 8000, must=["26"], scripted_confirm=True,
     notes="'Since last month' is a 1-2 month range; the worker corrects to one month.")
case("A6", A, ["paisa nahi mila", "2 mahine alternate din", "800 roz", "advance nahi", "20000 mile"],
     30, 800, 0, 20000, must=["30"], notes="Alternate days = 3.5/week; 2 x 4.33 x 3.5 = 30.")
case("A7", A, ["mazdoori baaki hai", "2 mahine, sirf Sunday chhutti", "600 roz", "nahi", "25000"],
     52, 600, 0, 25000, must=["52"], notes="Only Sunday off = 6/week; 2 x 4.33 x 6 = 52.")
case("A8", A, ["paise kam diye", "do hafte roz kaam kiya", "650", "advance nahi", "7000"],
     14, 650, 0, 7000, must=["14"], notes="Two weeks every day = 14.")
case("A9", A, ["pagar nahi mili", "4 hafte, hafte mein 5 din", "700 roz", "500 advance", "10000 mile"],
     20, 700, 500, 10000, must=["20"], notes="4 weeks x 5 = 20.")
case("A10", A, ["hisaab karna hai", "1 mahina kaam kiya", "roz 550", "advance nahi", "10000"],
     26, 550, 0, 10000, must=["26"], notes="One month x 26.")
case("A11", A, ["paise nahi diye", "3 mahine, hafte mein 6 din", "600 roz", "2000 advance", "40000 mile"],
     78, 600, 2000, 40000, must=["78"], notes="3 x 4.33 x 6 = 77.9 -> 78.")
case("A12", A, ["seth ne paise roke", "dedh mahina", "500 roz", "advance nahi", "15000"],
     39, 500, 0, 15000, must=["39"], notes="1.5 months x 26 = 39.")
case("A13", A, ["paise baaki", "5-6 hafte", "600 roz", "advance nahi", "15000 mile"],
     36, 600, 0, 15000, must=["36", "5-6"], notes="Week range: upper end used and named; worker agrees.")
case("A14", A, ["paise nahi mile", "ek hafta", "700 roz", "nahi", "3000"],
     6, 700, 0, 3000, must=["6 din"], notes="One week, 6 days assumed.")
case("A15", A, ["pagar kam aayi", "teen mahine, hafte mein 5 din", "500 roz", "nahi", "25000"],
     65, 500, 0, 25000, must=["65"], notes="3 x 4.33 x 5 = 65.")

# ---------- B: the rate is per month, per week, per trip, a range, or 'market rate' ----------
case("B1", B, ["paise nahi mile", "20 din", "mahine ke 15000 tay the", "advance nahi", "5000 mile"],
     20, 577, 0, 5000, must=["577"], notes="15000/month / 26 = 577/day.")
case("B2", B, ["hisaab chahiye", "12 din", "hafte ke 3500", "nahi", "4000"],
     12, 583, 0, 4000, must=["583"], notes="3500/week / 6 = 583.")
case("B3", B, ["paise baaki hain", "10 din", "per trip 200", "4 trip roz", "advance nahi", "5000"],
     10, 800, 0, 5000, must=["trip"], notes="Per trip: one question for trips/day, then 200 x 4.")
case("B4", B, ["paisa nahi mila", "6 din", "600-700 roz", "700", "nahi", "3000"],
     6, 700, 0, 3000, must=["600 ya 700"], scripted_confirm=True, notes="Rate range asked once.")
case("B5", B, ["paise kam diye", "8 din", "market rate jitna", "500 roz", "advance nahi", "2000"],
     8, 500, 0, 2000, must=[], notes="'Market rate' is not a number: noted, then asked for the agreed rate.")
case("B6", B, ["pagar nahi mili", "26 din", "mahine ka 12000", "1000 advance", "8000 mile"],
     26, 462, 1000, 8000, must=["462"], notes="12000 / 26 = 462.")
case("B7", B, ["paise nahi diye", "6 din", "hafte ka 4200", "nahi", "2000"],
     6, 700, 0, 2000, must=["700"], notes="4200 / 6 = 700.")
case("B8", B, ["hisaab karo", "5 din", "ek trip ke 150", "din mein 5 trip", "nahi", "1000"],
     5, 750, 0, 1000, must=["750"], notes="150 x 5 trips.")
case("B9", B, ["paise baaki", "10 din", "500-550 roz", "550", "advance nahi", "4000"],
     10, 550, 0, 4000, must=["500 ya 550"], scripted_confirm=True, notes="Range answered with the upper end.")
case("B10", B, ["paise nahi mile", "15 din", "18000 mahina", "nahi", "6000"],
     15, 692, 0, 6000, must=["692"], notes="18000 / 26 = 692.")
case("B11", B, ["paise kam", "9 din", "roz 650", "nahi", "5000"],
     9, 650, 0, 5000, notes="Plain daily rate: no confirmation detour.")
case("B12", B, ["pagar baaki", "12 din", "har hafte 3000", "nahi", "3000"],
     12, 500, 0, 3000, must=["500"], notes="3000 / 6 = 500.")
case("B13", B, ["paise nahi mile", "4 din", "trip ka 300, din mein 3 trip", "nahi", "1000"],
     4, 900, 0, 1000, must=["900"], notes="Trip rate and trips/day in one line.")
case("B14", B, ["paise nahi diye", "7 din", "800-900", "800", "nahi", "2000"],
     7, 800, 0, 2000, must=["800 ya 900"], scripted_confirm=True, notes="Range answered with the lower end.")
case("B15", B, ["hisaab chahiye", "20 din", "salary 10000 mahine ki", "nahi", "4000"],
     20, 385, 0, 4000, must=["385"], notes="10000 / 26 = 385.")

# ---------- C: deductions, bonus, non-cash and split payments ----------
case("C1", C, ["6 din, 700 roz", "khane ke 200 kate", "advance nahi", "3000 mile"],
     6, 700, 0, 3000, deductions=200, notes="Food deduction lowers what was owed.")
case("C2", C, ["8 din kaam kiya", "600 roz", "tools ka 500 kata", "advance nahi", "2000 mile"],
     8, 600, 0, 2000, deductions=500, notes="Tool charge deducted.")
case("C3", C, ["10 din", "500 roz", "bonus 1000 bola tha", "advance nahi", "4000 mile"],
     10, 500, 0, 4000, bonus=1000, notes="Promised bonus is part of what is owed.")
case("C4", C, ["5 din", "700 roz", "advance nahi", "2000 cash aur 1000 UPI mila"],
     5, 700, 0, 3000, notes="Cash + UPI add up to one payments total.")
case("C5", C, ["paise nahi mile", "12 din", "roz 600", "rehne ke 1000 kate", "nahi", "3000"],
     12, 600, 0, 3000, deductions=1000, notes="Lodging deduction.")
case("C6", C, ["7 din, 800 roz", "bonus 500 dene ko bola tha", "advance nahi", "4000"],
     7, 800, 0, 4000, bonus=500, notes="Bonus after days and rate.")
case("C7", C, ["9 din", "550 roz", "advance nahi", "1500 cash aur 1500 UPI"],
     9, 550, 0, 3000, notes="Half cash half UPI, both amounts said.")
case("C8", C, ["15 din", "roz 500", "khane ke 300 kate", "1000 advance", "4000 mile"],
     15, 500, 1000, 4000, deductions=300, notes="Deduction and advance in one case.")
case("C9", C, ["6 din, 900 roz", "advance nahi", "2000 mile aur 1000 baad mein mile"],
     6, 900, 0, 3000, notes="Two payments in one line.")
case("C10", C, ["10 din", "600 roz", "bonus 2000 bola tha", "khane ke 500 kate", "nahi", "5000"],
     10, 600, 0, 5000, deductions=500, bonus=2000, notes="Bonus and deduction together.")
case("C11", C, ["4 din", "1000 roz", "tools ka 200 kata", "nahi", "1000"],
     4, 1000, 0, 1000, deductions=200, notes="Tools charge, small case.")
case("C12", C, ["20 din", "400 roz", "advance nahi", "3000 UPI aur 2000 cash mila"],
     20, 400, 0, 5000, notes="UPI first then cash.")
case("C13", C, ["8 din", "750 roz", "bonus 1000 bola tha", "500 advance", "3000"],
     8, 750, 500, 3000, bonus=1000, notes="Bonus with an advance.")
case("C14", C, ["5 din", "600 roz", "uniform ke 300 kate", "nahi", "2000"],
     5, 600, 0, 2000, deductions=300, notes="Uniform charge deducted.")
case("C15", C, ["12 din", "700 roz", "nahi", "5000 mile", "haan"],
     12, 700, 0, 5000, notes="Control: no extras.")

# ---------- D: is this money an advance? ----------
case("D1", D, ["10 din", "600 roz", "manager se 5000 liya tha", "haan, kaatenge", "nahi aur kuch nahi mila"],
     10, 600, 5000, 0, must=["5000"], scripted_confirm=True,
     notes="Money taken from the manager: asked whether it comes out of the wages.")
case("D2", D, ["6 din", "700 roz", "5000 udhaar liya tha", "nahi, woh alag hai", "3000 mile"],
     6, 700, 0, 3000, must=["5000"], scripted_confirm=True,
     notes="A separate loan is not an advance against these wages.")
case("D3", D, ["8 din", "500 roz", "advance 1000 mila tha", "2000 mile"],
     8, 500, 1000, 2000, notes="Plainly an advance.")
case("D4", D, ["10 din", "700 roz", "seth se 2000 liye the", "haan katenge", "3000 mile"],
     10, 700, 2000, 3000, must=["2000"], scripted_confirm=True, notes="Money taken from the boss, will be cut.")
case("D5", D, ["5 din", "600 roz", "advance nahi", "kuch nahi mila"],
     5, 600, 0, 0, notes="Nothing paid at all.")
case("D6", D, ["12 din", "500 roz", "pehle 3000 advance liya", "2000 mile"],
     12, 500, 3000, 2000, notes="Advance taken before the work.")
case("D7", D, ["7 din", "800 roz", "advance 0", "4000"],
     7, 800, 0, 4000, notes="Zero said as a digit.")
case("D8", D, ["9 din", "600 roz", "thekedar se 1000 liya tha", "haan, kaatenge", "2000"],
     9, 600, 1000, 2000, must=["1000"], scripted_confirm=True, notes="Contractor money, will be cut.")
case("D9", D, ["10 din", "500 roz", "advance nahi liya", "2000 aur 1000 mile"],
     10, 500, 0, 3000, notes="Two payments.")
case("D10", D, ["6 din", "650 roz", "500 advance", "nahi kuch nahi mila"],
     6, 650, 500, 0, notes="Advance only.")
case("D11", D, ["15 din", "600 roz", "manager se 3000 liya tha", "nahi, woh wapas kar diya", "5000 mile"],
     15, 600, 0, 5000, must=["3000"], scripted_confirm=True, notes="Already repaid: not counted.")
case("D12", D, ["4 din", "900 roz", "nahi", "1000 mile"],
     4, 900, 0, 1000, notes="Control.")
case("D13", D, ["20 din", "500 roz", "advance 2000", "6000"],
     20, 500, 2000, 6000, notes="Advance said with the word.")
case("D14", D, ["8 din", "700 roz", "do hazaar advance", "teen hazaar"],
     8, 700, 2000, 3000, notes="Words for numbers.")
case("D15", D, ["6 din", "600 roz", "advance nahi mila tha", "1500"],
     6, 600, 0, 1500, notes="Control.")

# ---------- E: context and emotion (an acknowledgement line, then the next question) ----------
case("E1", E, ["paise nahi mile", "pichhle hafte hospital mein tha, 6 din kaam kiya", "700 roz", "nahi", "3000"],
     6, 700, 0, 3000, must=["dukh hua"], notes="Health: one line, and 'last week' is not a period.")
case("E2", E, ["thekedar dhamki deta hai", "6 din", "700 roz", "nahi", "3000"],
     6, 700, 0, 3000, must=["Dara mat"], notes="Threat.")
case("E3", E, ["tum kaun ho", "6 din", "700 roz", "nahi", "3000"],
     6, 700, 0, 3000, must=["PagarSaathi"], notes="Identity question.")
case("E4", E, ["yeh free hai kya", "8 din", "600 roz", "nahi", "2000"],
     8, 600, 0, 2000, must=["free"], notes="Cost question.")
case("E5", E, ["mera data safe hai?", "10 din", "500 roz", "nahi", "3000"],
     10, 500, 0, 3000, must=["delete"], notes="Privacy question.")
case("E6", E, ["bahut pareshan hoon", "6 din", "700 roz", "nahi", "3000"],
     6, 700, 0, 3000, must=["Tension mat"], notes="Emotion.")
case("E7", E, ["paise nahi mile", "5 din", "bimar tha isliye kam din", "600 roz", "nahi", "1000"],
     5, 600, 0, 1000, must=["dukh hua"], notes="Health mid-way, after the days were given.")
case("E8", E, ["7 din", "seth bolta hai kaam se nikaal dunga", "800 roz", "nahi", "2000"],
     7, 800, 0, 2000, must=["Dara mat"], notes="Threat mid-way.")
case("E9", E, ["Teen saal se unke saath hoon, pichhle hafte bimar bhi tha.", "6 din", "700 roz", "nahi", "3000"],
     6, 700, 0, 3000, must=["dukh hua"], notes="Tenure and illness: neither is a day count.")
case("E10", E, ["meri pagar badhao", "10 din", "600 roz", "nahi", "4000"],
     10, 600, 0, 4000, notes="A raise is out of scope; the agent says so in one line and continues.")

# ---------- F: corrections and contradictions ----------
case("F1", F, ["6 din", "arre 6 nahi 5", "700 roz", "nahi", "2000"],
     5, 700, 0, 2000, notes="Correction replaces the old number, no question.")
case("F2", F, ["6 din", "700 roz", "pehle 700 bola tha, 650 sahi hai", "nahi", "2000"],
     6, 650, 0, 2000, notes="Rate correction.")
case("F3", F, ["6 din", "700 roz", "nahi", "3000", "nahi, din 5 the", "haan"],
     5, 700, 0, 3000, scripted_confirm=True, notes="Correction at the read-back.")
case("F4", F, ["8 din", "5 din", "5", "600 roz", "nahi", "1000"],
     5, 600, 0, 1000, must=["kaunsa"], scripted_confirm=True,
     notes="Two different day counts: the agent asks which, does not overwrite.")
case("F5", F, ["10 din", "500 roz", "600 roz", "600", "nahi", "3000"],
     10, 600, 0, 3000, must=["kaunsa"], scripted_confirm=True, notes="Two different rates: asked which.")
case("F6", F, ["7 din nahi 8 din", "600 roz", "nahi", "2000"],
     8, 600, 0, 2000, notes="Correction inside one line.")
case("F7", F, ["6 din", "700", "advance 500", "nahi advance nahi tha", "3000"],
     6, 700, 0, 3000, scripted_confirm=True, notes="Advance withdrawn.")
case("F8", F, ["9 din", "600 roz", "nahi", "2000", "nahi, 3000 mile the", "haan"],
     9, 600, 0, 3000, scripted_confirm=True, notes="Payment corrected at read-back.")
case("F9", F, ["12 din", "500 nahi 550 roz", "nahi", "3000"],
     12, 550, 0, 3000, notes="Rate corrected in one line.")
case("F10", F, ["teen hafte", "hafte mein 5 din", "haan", "700 roz", "nahi", "5000"],
     15, 700, 0, 5000, must=["15"], scripted_confirm=True, notes="Weeks refined by frequency before confirming.")
case("F11", F, ["5 din", "700 roz", "nahi", "1000", "nahi, roz 750 the", "haan"],
     5, 750, 0, 1000, scripted_confirm=True, notes="Rate corrected at read-back.")
case("F12", F, ["2 mahine", "nahi, sirf 40 din", "600 roz", "nahi", "10000"],
     40, 600, 0, 10000, scripted_confirm=True, notes="Derived 52 rejected with the real count.")
case("F13", F, ["6 din", "same 6 din", "700 roz", "nahi", "3000"],
     6, 700, 0, 3000, notes="Repeating the same number is not a conflict.")
case("F14", F, ["10 din", "600 roz", "1000 advance", "nahi 1500 advance", "3000"],
     10, 600, 1500, 3000, scripted_confirm=True, notes="Advance corrected.")
case("F15", F, ["mahine ke 15000", "20 din", "haan", "nahi", "5000"],
     20, 577, 0, 5000, must=["577"], scripted_confirm=True, notes="Monthly rate first, days after, then a yes.")

# ---------- G: number formats ----------
case("G1", G, ["6 din", "700 roz", "500", "3000"], 6, 700, 500, 3000, notes="Digits.")
case("G2", G, ["chhe din", "saat sau", "paanch sau", "teen hazaar"], 6, 700, 500, 3000, notes="Hinglish words.")
case("G3", G, ["६ दिन", "७०० रोज़", "५००", "३०००"], 6, 700, 500, 3000, notes="Devanagari numerals.")
case("G4", G, ["six days", "seven hundred per day", "five hundred", "three thousand"],
     6, 700, 500, 3000, notes="English words.")
case("G5", G, ["", "6 din", "700 roz", "500", "3000"], 6, 700, 500, 3000, notes="Silence first.")
case("G6", G, ["6-7 din", "7", "700 roz", "500", "3000"], 7, 700, 500, 3000, scripted_confirm=True,
     notes="Mixed range for days: asked once.")
case("G7", G, ["chhah din", "700", "nahi", "teen hazaar"], 6, 700, 0, 3000, notes="Spelling variant.")
case("G8", G, ["das din", "paanch sau", "do sau", "teen hazaar"], 10, 500, 200, 3000, notes="Words.")
case("G9", G, ["छह दिन", "सात सौ", "पांच सौ", "तीन हज़ार"], 6, 700, 500, 3000, notes="Devanagari words.")
case("G10", G, ["6 days", "700 rupees", "500", "3000"], 6, 700, 500, 3000, notes="English unit words.")
case("G11", G, ["Chhe din kaam kiya, saat sau roz, paanch sau advance, teen hazaar mila"],
     6, 700, 500, 3000, notes="All four in one line.")
case("G12", G, ["8 din, 650 roz", "nahi", "4000"], 8, 650, 0, 4000, notes="Two in one line.")
case("G13", G, ["dhai hazaar mahina", "10 din", "haan", "nahi", "500"], 10, 96, 0, 500,
     must=["96"], scripted_confirm=True, notes="2500/month / 26 = 96 (very low wage, still computed).")
case("G14", G, ["15 din", "₹600", "nil", "₹5000"], 15, 600, 0, 5000, notes="Rupee sign; 'nil' is zero.")
case("G15", G, ["nau din", "aath sau", "hazaar", "do hazaar"], 9, 800, 1000, 2000, notes="Words, bare 'hazaar'.")

# ---------- H: disputes and legal questions ----------
case("H1", H, ["court jaunga", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000, must=["shikayat"],
     notes="Court: acknowledged, the hisaab comes first.")
case("H2", H, ["proof chahiye", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000, must=["record"],
     notes="Proof: the case record is the proof.")
case("H3", H, ["contractor manna kare to kya", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000,
     notes="Refusal question.")
case("H4", H, ["kitne din mein paisa milega", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000,
     notes="Timing question.")
case("H5", H, ["6 din", "court jaunga", "700 roz", "nahi", "3000"], 6, 700, 0, 3000, must=["shikayat"],
     notes="Court mid-way.")
case("H6", H, ["8 din", "600 roz", "proof chahiye", "nahi", "2000"], 8, 600, 0, 2000, must=["record"],
     notes="Proof mid-way.")
case("H7", H, ["paise nahi mile, police mein jaunga", "6 din", "700 roz", "nahi", "3000"],
     6, 700, 0, 3000, notes="Police.")
case("H8", H, ["labour office jana hai", "10 din", "500 roz", "nahi", "3000"], 10, 500, 0, 3000,
     notes="Labour office.")
case("H9", H, ["6 din", "700 roz", "contractor manna kare to", "nahi", "3000"], 6, 700, 0, 3000,
     notes="Refusal question mid-way.")
case("H10", H, ["kitne din mein paisa aayega", "5 din", "600 roz", "nahi", "1000"], 5, 600, 0, 1000,
     notes="Timing.")
case("H11", H, ["case karna hai", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000, notes="Case.")
case("H12", H, ["likh ke chahiye", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000, notes="Written proof.")
case("H13", H, ["thekedar bolta hai paise nahi dunga", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000,
     notes="Refusal statement.")
case("H14", H, ["12 din", "600 roz", "court jana padega kya", "nahi", "4000"], 12, 600, 0, 4000,
     must=["shikayat"], notes="Court question late.")
case("H15", H, ["6 din", "700 roz", "500", "3000", "kab tak milega"], 6, 700, 500, 3000,
     notes="Timing question after the read-back.")

# ---------- held-out: written after the corpus fixes, run once, never tuned on ----------
MAIN = list(CASES)
CASES.clear()
case("X1", A, ["paise baaki", "chaar mahine, hafte mein chhe din", "600 roz", "advance nahi", "50000 mile"],
     104, 600, 0, 50000, must=["104"], notes="4 x 4.33 x 6 = 103.9 -> 104.")
case("X2", A, ["hisaab", "do hafte, hafte mein 5 din", "700 roz", "nahi", "5000"], 10, 700, 0, 5000, must=["10"])
case("X3", A, ["paise nahi mile", "2-3 hafte", "500 roz", "nahi", "6000"], 18, 500, 0, 6000, must=["18"],
     notes="Range: upper end (3 weeks x 6).")
case("X4", A, ["pagar baaki", "ek mahina, sirf Sunday chhutti", "650 roz", "nahi", "10000"],
     26, 650, 0, 10000, must=["26"], notes="1 x 4.33 x 6 = 26.")
case("X5", B, ["paise nahi mile", "10 din", "mahine ki 13000 salary", "nahi", "2000"], 10, 500, 0, 2000,
     must=["500"], notes="13000 / 26 = 500.")
case("X6", B, ["hisaab", "6 din", "hafte ke 4800", "nahi", "1000"], 6, 800, 0, 1000, must=["800"])
case("X7", B, ["paise kam", "8 din", "700-800 roz", "750", "nahi", "2000"], 8, 750, 0, 2000, scripted_confirm=True,
     notes="Range answered with a number inside it.")
case("X8", C, ["5 din, 600 roz", "khane ke 250 kaat liye", "nahi", "1000"], 5, 600, 0, 1000, deductions=250)
case("X9", C, ["7 din", "500 roz", "bonus 700 bola tha", "nahi", "2000"], 7, 500, 0, 2000, bonus=700)
case("X10", C, ["6 din", "800 roz", "nahi", "1000 UPI aur 2000 cash"], 6, 800, 0, 3000)
case("X11", D, ["9 din", "600 roz", "thekedar se 2000 liya tha", "haan katenge", "1000"], 9, 600, 2000, 1000,
     scripted_confirm=True)
case("X12", D, ["10 din", "500 roz", "bhai se 1000 udhaar liya, woh alag hai", "2000 mile"], 10, 500, 0, 2000,
     notes="Private loan said with 'alag'; advance never said, so it is asked.")
case("X13", E, ["mujhe darr lag raha hai", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000)
case("X14", E, ["kya yeh sarkari app hai", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000)
case("X15", F, ["7 din", "nahi nahi 6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000)
case("X16", F, ["6 din", "700 roz", "500 advance", "galti se bola, 300 advance", "2000"], 6, 700, 300, 2000,
     scripted_confirm=True)
case("X17", G, ["saat din", "chhe sau pachaas", "nahi", "do hazaar"], 7, 650, 0, 2000)
case("X18", G, ["७ दिन", "६५० रोज़", "नहीं", "२०००"], 7, 650, 0, 2000)
case("X19", H, ["shikayat karni hai", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000)
case("X20", H, ["thekedar bhaag gaya", "6 din", "700 roz", "nahi", "3000"], 6, 700, 0, 3000)
HOLDOUT = list(CASES)
CASES[:] = MAIN

if __name__ == "__main__":
    counts = {}
    for c in CASES:
        counts[c["class"][0]] = counts.get(c["class"][0], 0) + 1
    assert len(CASES) == 115, len(CASES)
    assert counts == {"A": 15, "B": 15, "C": 15, "D": 15, "E": 10, "F": 15, "G": 15, "H": 15}, counts
    assert len({c["id"] for c in CASES}) == 115
    with open(os.path.join(ROOT, "test_corpus.json"), "w", encoding="utf-8") as f:
        json.dump(CASES, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "test_corpus_holdout.json"), "w", encoding="utf-8") as f:
        json.dump(HOLDOUT, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(CASES)} cases: {counts}; held-out: {len(HOLDOUT)}")
