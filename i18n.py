"""Agent lines in the worker's language.

Hindi (Roman shown + Devanagari spoken) is the source. Marathi has full translations of every fixed
line, the read-back and the result. Bengali, Tamil, Telugu and Bhojpuri are beta: the LLM policy
replies in that language, but Python's fixed lines (read-back, result, choices) stay Hindi and are
spoken with the Hindi voice, so the amounts are never in a voice that misreads them.

localise(session, line, lang) -> (line, lang_of_line). lang_of_line picks the voice.
"""
_MR = None


def _table():
    """Hindi shown text -> (Marathi shown, Marathi spoken). Built lazily (conversation imports us)."""
    global _MR
    if _MR is not None:
        return _MR
    import conversation as c
    m = {
        c.GREETING: "नमस्कार, मी पगार साथी. सांगा, पैशांबद्दल काय अडचण आहे?",
        c.STATES[c.ASK_DAYS]["question_hi"]: "तुम्ही किती दिवस काम केलं?",
        c.STATES[c.ASK_DAYS]["simpler"]: "किती दिवस काम केलं? फक्त आकडा सांगा, जसं सहा दिवस.",
        c.STATES[c.ASK_DAYS]["example"]: "आठवड्याचा विचार करा: ज्या आठवड्याचे पैसे बाकी आहेत, त्यात किती दिवस कामाला गेलात?",
        c.STATES[c.ASK_RATE]["question_hi"]: "रोजची मजुरी किती ठरली होती?",
        c.STATES[c.ASK_RATE]["simpler"]: "एका दिवसाचे किती रुपये ठरले होते? जसं सातशे रुपये.",
        c.STATES[c.ASK_RATE]["example"]: "ठेकेदाराने एका दिवसाचे किती सांगितले होते? फक्त रुपये सांगा.",
        c.STATES[c.ASK_ADVANCE]["question_hi"]: "आधी काही ॲडव्हान्स मिळाला होता का?",
        c.STATES[c.ASK_ADVANCE]["simpler"]: "कामाच्या आधी किती पैसे मिळाले होते? नसतील तर नाही म्हणा.",
        c.STATES[c.ASK_ADVANCE]["example"]: "काम सुरू होण्याआधी किंवा मध्ये, मजुरीतून कापले जाणारे किती पैसे घेतले होते?",
        c.STATES[c.ASK_PAYMENTS]["question_hi"]: "आतापर्यंत किती पैसे मिळाले?",
        c.STATES[c.ASK_PAYMENTS]["simpler"]: "ॲडव्हान्स सोडून आतापर्यंत किती रुपये मिळाले? काही नाही मिळालं तर नाही म्हणा.",
        c.STATES[c.ASK_PAYMENTS]["example"]: "या कामासाठी हातात किती रुपये आले आहेत? काही नाही आलं तर काही नाही म्हणा.",
        c.STATES[c.CONFIRM]["simpler"]: "हे सगळं बरोबर आहे का? हो किंवा नाही म्हणा.",
        c.STATES[c.ASK_SEND]["simpler"]: "मेसेज पाठवू, तक्रारीचा मसुदा बनवू, की फक्त केस सेव्ह करू? एक सांगा.",
        c.RESTART: "ठीक आहे, पुन्हा सुरू करूया. तुम्ही किती दिवस काम केलं?",
        c.PREVIEW: "हा मेसेज आहे. बघून घ्या, मग व्हॉट्सॲपवर पाठवा हे बटण दाबा.",
        c.NO_SEND: "ठीक आहे, मेसेज पाठवत नाही. तुमचा हिशोब स्क्रीनवर आहे.",
        c.SENT: "व्हॉट्सॲप उघडलं आहे. मेसेज पाठवा. धन्यवाद.",
        c.DONE_LINE: "हिशोब झाला. धन्यवाद.",
        c.CHOICES: "आता काय करू: मेसेज पाठवू, तक्रार करू, की फक्त केस सेव्ह करू?",
        c.SAVED: "केस सेव्ह झाली. हॅश कार्डवर आहे. नंतर मेसेज किंवा तक्रारही करू शकता.",
        c.ESCALATED: "तक्रारीचा मसुदा स्क्रीनवर आहे. कॉपी करून समाधान पोर्टलवर किंवा कामगार कार्यालयात द्या.",
        c.EXTRAS_Q: "ठीक आहे. किती तास ओव्हरटाइम केला, एका तासाचे किती, आणि किती कपात झाली?",
        c.EXTRAS_SIMPLER: "जसं: दहा तास ओव्हरटाइम, शंभर रुपये तास, दोनशे कपात. काही नसेल तर नाही म्हणा.",
        c.FOLLOWUP_Q: "नमस्कार, पगार साथी पुन्हा. मागच्या केसबद्दल: ठेकेदार किंवा मॅनेजर काय म्हणाले?",
        c.DELETE_ASK: "नक्की केस डिलीट करू? ती परत येणार नाही. हो किंवा नाही म्हणा.",
        c.DELETED: "केस डिलीट झाली. तिचा कोणताही रेकॉर्ड आता नाही.",
        c.NOT_DELETED: "ठीक आहे, केस डिलीट केली नाही. ",
        c.NO_CASE: "आत्ता कोणतीही सेव्ह केलेली केस नाही. ",
        c.ASSIST_NUMBER: "काही हरकत नाही. एखाद्या साथीदाराची मदत घ्या. ",
        c.ASSIST_ZERO: "काही हरकत नाही, आत्तासाठी शून्य धरूया. कन्फर्म करताना बदलू शकता. ",
        c.WHAT_WRONG: "काय चुकलं? दिवस, रोजची मजुरी, ॲडव्हान्स की मिळालेले पैसे: बरोबर आकडा सांगा.",
        c.SORRY: "माफ करा, नीट समजलं नाही. ",
        c.HELPLINE: "आत्ता पूर्ण हिशोब झाला नाही. तुम्ही सांगितलेलं स्क्रीनवर आहे. एखादा साथीदार, युनियन किंवा "
                    "इंडिया लेबरलाइन 1800 1800 999 कडून मदत घ्या.",
    }
    _MR = {hi[0]: (mr, mr) for hi, mr in m.items()}
    return _MR


def _pieces(shown):
    """Split a joined line back into known fixed lines (longest match first)."""
    table = _table()
    out, rest = [], shown
    while rest:
        for key in sorted(table, key=len, reverse=True):
            if rest.startswith(key):
                out.append(table[key][0])
                rest = rest[len(key):].lstrip()
                break
        else:
            if "\u0900" <= rest[0] <= "\u097F":    # already Marathi (readback_mr / result_mr)
                out.append(rest)
                return out
            return None
    return out


def localise(session, line, lang=None):
    """(shown, spoken) in the session language where a translation exists, and the line's language."""
    if lang:                              # the LLM already wrote this line in the worker's language
        return line, lang
    want = session.get("language", "hi")
    if want == "mr":
        if line[1] and any("ऀ" <= ch <= "ॿ" for ch in line[0]):
            return line, "mr"             # already Marathi (readback_mr / result_mr)
        parts = _pieces(line[0])
        if parts:
            text = " ".join(p.strip() for p in parts)
            return (text, text), "mr"
    return line, "hi"                     # Hindi, and the Hindi fallback for beta languages


def _inr(n):
    return f"{n} रुपये"


def readback_mr(f, offer_extras=False, extras=None):
    adv = f"{_inr(f['advance'])} ॲडव्हान्स" if f["advance"] else "ॲडव्हान्स नाही"
    paid = f"{_inr(f['payments'])} मिळाले" if f["payments"] else "आतापर्यंत काही मिळाले नाही"
    ex = ""
    if extras and extras.get("overtime_hours"):
        ex += f", {extras['overtime_hours']} तास ओव्हरटाइम {extras['overtime_rate']} रुपये तास"
    if extras and extras.get("deductions"):
        ex += f", {_inr(extras['deductions'])} कपात"
    text = f"कन्फर्म करतो: {f['days']} दिवस, रोज {_inr(f['rate'])}, {adv}, {paid}{ex}. बरोबर आहे का?"
    if offer_extras:
        text += " ओव्हरटाइम किंवा कपात असेल तर तीही सांगा."
    return (text, text)


def result_mr(case):
    parts = [f"एकूण कमाई {_inr(case['expected'])}."]
    if case["received"]:
        parts.append(f"ॲडव्हान्स {_inr(case['advance'])}, आतापर्यंत मिळाले {_inr(case['payments'])}, "
                     f"एकूण मिळाले {_inr(case['received'])}.")
    else:
        parts.append("आतापर्यंत काही मिळाले नाही.")
    if case["outstanding"] <= 0:
        parts.append("हिशोबानुसार कोणतेही पैसे बाकी नाहीत. केस सेव्ह झाली.")
    else:
        parts.append(f"बाकी {_inr(case['outstanding'])}. आता काय करू: मेसेज पाठवू, तक्रार करू, की फक्त केस सेव्ह करू?")
    text = " ".join(parts)
    return (text, text)
