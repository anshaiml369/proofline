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


def calculate_wages(days, rate, advance=0, payments=0):
    """expected = days × rate; received = advance + payments; outstanding = max(0, expected − received)."""
    days = _whole("days", days)
    rate = _whole("rate", rate)
    advance = _whole("advance", advance or 0)
    payments = _whole("payments", payments or 0)

    expected = days * rate
    received = advance + payments
    outstanding = max(0, expected - received)
    return {
        "days": days,
        "rate": rate,
        "advance": advance,
        "payments": payments,
        "expected": expected,
        "received": received,
        "outstanding": outstanding,
        "overpaid": max(0, received - expected),
        "breakdown": breakdown_lines(days, rate, advance, payments, expected, outstanding),
    }


def breakdown_lines(days, rate, advance, payments, expected, outstanding):
    """Display strings for the calculation card; the browser only renders these, it does no maths."""
    return [
        {"label": "Kul kamaai", "math": f"{days} din × {format_inr(rate)}", "amount": format_inr(expected)},
        {"label": "Advance", "math": "minus", "amount": "− " + format_inr(advance)},
        {"label": "Ab tak mila", "math": "minus", "amount": "− " + format_inr(payments)},
        {"label": "Baaki", "math": "", "amount": format_inr(outstanding), "total": True},
    ]


def payment_request(result):
    """Hinglish WhatsApp message to the contractor. Only uses numbers already calculated above."""
    return (
        "Namaste Thekedar ji,\n"
        "Mera mazdoori ka hisaab:\n"
        f"• Kaam: {result['days']} din × {format_inr(result['rate'])} = {format_inr(result['expected'])}\n"
        f"• Advance mila: {format_inr(result['advance'])}\n"
        f"• Ab tak mila: {format_inr(result['payments'])}\n"
        f"• Kul mila: {format_inr(result['received'])}\n"
        f"Baaki: {format_inr(result['outstanding'])}\n\n"
        f"Kripya baaki {format_inr(result['outstanding'])} jaldi de dijiye. Dhanyavaad.\n"
        "(PagarSaathi se hisaab)"
    )
