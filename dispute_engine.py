"""Rule-based dispute scoring. No model calls: the same evidence card always gets the same score.

The AI only extracts the evidence card. These fixed rules score it. The platform makes the final call.
"""

KNOWN_LOCATIONS = {"door", "reception", "security", "neighbor"}
NON_DELIVERY_PHRASES = (
    "not delivered", "never delivered", "not received", "never received",
    "didn't receive", "did not receive", "didn't get", "did not get", "never arrived",
)


def classify_claim(customer_claim):
    claim = (customer_claim or "").strip().lower()
    if not claim:
        return "none"
    if any(phrase in claim for phrase in NON_DELIVERY_PHRASES):
        return "non_delivery"
    return "contents"


def evidence_strength(card):
    """Additive score: OTP +40, GPS match +30, confidence not low +20, named handover location +10."""
    otp = card.get("otp_confirmed") is True
    gps = card.get("gps_matched") is True
    confident = card.get("confidence", "low") != "low"
    location = card.get("handover_location")
    location_known = location in KNOWN_LOCATIONS

    score = (40 if otp else 0) + (30 if gps else 0) + (20 if confident else 0) + (10 if location_known else 0)

    parts = [
        "OTP confirmed" if otp else "OTP not confirmed",
        "GPS matched" if gps else "GPS did not match",
        f"{card.get('confidence', 'low')}-confidence spoken account",
    ]
    reason = ", ".join(parts[:2]) + ", " + parts[2]
    if location_known:
        reason += f" of a handover at {location}."
    elif location == "other":
        reason += " of a handover at an unusual place."
    else:
        reason += " with no clear handover location."
    return min(score, 100), reason[0].upper() + reason[1:]


def score_dispute(card, customer_claim=""):
    strength, reason = evidence_strength(card)
    band = "high" if strength >= 80 else "medium" if strength >= 50 else "low"
    claim_type = classify_claim(customer_claim)
    status = card.get("delivery_status")

    # Safeguards: the rider's own words, or a claim a handover record can't address, override the score.
    if status == "failed":
        recommendation = "favor_customer" if claim_type == "non_delivery" else "inconclusive"
        reason = "The rider's own record says the delivery failed."
    elif status == "partial":
        recommendation = "inconclusive"
        reason = "The rider reports only a partial handover."
    elif claim_type == "contents":
        recommendation = "inconclusive"
        reason = "Handover evidence cannot show what was inside the package."
    elif band == "high":
        recommendation = "favor_rider"
    elif band == "medium":
        recommendation = "inconclusive"
    else:
        recommendation = "favor_customer"

    return {"evidence_strength": strength, "recommendation": recommendation, "reasoning": reason}
