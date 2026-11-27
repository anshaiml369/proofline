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
    """Returns (score 0-100, band, reasoning citing the deciding signal)."""
    otp = card.get("otp_confirmed") is True
    gps = card.get("gps_matched") is True
    spoken = card.get("spoken_context") not in (None, "", "not_mentioned")
    location = card.get("handover_location")
    location_known = location in KNOWN_LOCATIONS
    confidence = card.get("confidence", "low")
    obstacle = card.get("obstacle")

    if not otp or not spoken:
        score = 20 + (15 if gps else 0) + (14 if spoken else 0)
        reason = "OTP was not confirmed at handover." if not otp else "Rider gave no spoken account of the handover."
        return score, "low", reason

    if gps and location_known and confidence != "low" and obstacle != "customer_unavailable":
        score = 80 + (10 if confidence == "high" else 0) + (10 if obstacle == "none" else 0)
        reason = f"OTP confirmed, GPS matched, and the rider clearly described a handover at {location}."
        return score, "high", reason

    score = 50 + (10 if gps else 0) + (10 if location_known else 0) + (9 if confidence == "high" else 0)
    if obstacle == "customer_unavailable":
        reason = "OTP confirmed, but the rider reports the customer was unavailable at handover."
    elif confidence == "low":
        reason = "OTP confirmed, but the spoken handover description is unclear."
    elif not gps:
        reason = "OTP confirmed, but GPS did not match the drop location."
    elif location == "other":
        reason = "OTP confirmed, but the package was handed to an unusual place or person."
    else:
        reason = "OTP confirmed, but the rider did not say where the package was handed over."
    return score, "medium", reason


def score_dispute(card, customer_claim=""):
    strength, band, reason = evidence_strength(card)
    claim_type = classify_claim(customer_claim)
    status = card.get("delivery_status")

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
