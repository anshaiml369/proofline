"""All wage arithmetic lives here. The LLM never adds, subtracts or multiplies."""


def format_inr(amount):
    """4200 -> '₹4,200', 125000 -> '₹1,25,000' (Indian digit grouping)."""
    amount = int(amount)
    sign = "-" if amount < 0 else ""
    digits = str(abs(amount))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    return f"{sign}₹{digits}"


def _whole(name, value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a whole number of rupees/days, got {value!r}")
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    return value


def calculate_wages(days, rate, advance=0, payments=0, overtime_hours=0, overtime_rate=0, deductions=0):
    """expected = days × rate + overtime_hours × overtime_rate − deductions (never below 0);
    received = advance + payments; outstanding = max(0, expected − received).
    The optional fields default to 0, so the four-number case is unchanged."""
    days = _whole("days", days)
    rate = _whole("rate", rate)
    advance = _whole("advance", advance or 0)
    payments = _whole("payments", payments or 0)
    overtime_hours = _whole("overtime_hours", overtime_hours or 0)
    overtime_rate = _whole("overtime_rate", overtime_rate or 0)
    deductions = _whole("deductions", deductions or 0)

    base = days * rate
    overtime = overtime_hours * overtime_rate
    expected = max(0, base + overtime - deductions)
    received = advance + payments
    outstanding = max(0, expected - received)
    out = {
        "days": days,
        "rate": rate,
        "advance": advance,
        "payments": payments,
        "expected": expected,
        "received": received,
        "outstanding": outstanding,
        "overpaid": max(0, received - expected),
        "breakdown": breakdown_lines(days, rate, advance, payments, expected, outstanding,
                                     overtime_hours, overtime_rate, deductions),
    }
    if overtime or deductions:
        out.update(overtime_hours=overtime_hours, overtime_rate=overtime_rate, overtime=overtime,
                   deductions=deductions, base=base)
    return out


def breakdown_lines(days, rate, advance, payments, expected, outstanding, overtime_hours=0, overtime_rate=0, deductions=0):
    """Display strings for the calculation card; the browser only renders these, it does no maths.
    `icon` names a small picture for each line (calendar, clock, minus, rupee, wallet, check)."""
    lines = [{"label": "Kaam", "math": f"{days} din × {format_inr(rate)}", "amount": format_inr(days * rate), "icon": "calendar"}]
    if overtime_hours and overtime_rate:
        lines.append({"label": "Overtime", "math": f"{overtime_hours} ghante × {format_inr(overtime_rate)}",
                      "amount": "+ " + format_inr(overtime_hours * overtime_rate), "icon": "clock"})
    if deductions:
        lines.append({"label": "Katauti", "math": "minus", "amount": "− " + format_inr(deductions), "icon": "minus"})
    if len(lines) > 1:
        lines.append({"label": "Kul kamaai", "math": "", "amount": format_inr(expected), "icon": "rupee"})
    else:
        lines[0]["label"] = "Kul kamaai"
        lines[0]["icon"] = "rupee"
    lines += [
        {"label": "Advance", "math": "minus", "amount": "− " + format_inr(advance), "icon": "wallet"},
        {"label": "Ab tak mila", "math": "minus", "amount": "− " + format_inr(payments), "icon": "wallet"},
        {"label": "Baaki", "math": "", "amount": format_inr(outstanding), "total": True, "icon": "check"},
    ]
    return lines


def payment_request(result):
    """Hinglish WhatsApp message to the contractor. Only uses numbers already calculated above."""
    lines = ["Namaste Thekedar ji,", "Mera mazdoori ka hisaab:",
             f"• Kaam: {result['days']} din × {format_inr(result['rate'])} = {format_inr(result['days'] * result['rate'])}"]
    if result.get("overtime"):
        lines.append(f"• Overtime: {result['overtime_hours']} ghante × {format_inr(result['overtime_rate'])}"
                     f" = {format_inr(result['overtime'])}")
    if result.get("deductions"):
        lines.append(f"• Katauti: {format_inr(result['deductions'])}")
    if result.get("overtime") or result.get("deductions"):
        lines.append(f"• Kul kamaai: {format_inr(result['expected'])}")
    lines += [f"• Advance mila: {format_inr(result['advance'])}",
              f"• Ab tak mila: {format_inr(result['payments'])}",
              f"• Kul mila: {format_inr(result['received'])}",
              f"Baaki: {format_inr(result['outstanding'])}", "",
              f"Kripya baaki {format_inr(result['outstanding'])} jaldi de dijiye. Dhanyavaad.",
              "(PagarSaathi se hisaab)"]
    return "\n".join(lines)
