"""pytest tests/  — all wage arithmetic is in wage_math.py."""
import pytest

from wage_math import calculate_wages, format_inr, payment_request


@pytest.mark.parametrize("days, rate, advance, payments, outstanding", [
    (6, 700, 500, 3000, 700),     # the demo
    (5, 800, 0, 4000, 0),         # fully paid
    (10, 500, 200, 3000, 1800),
])
def test_outstanding(days, rate, advance, payments, outstanding):
    assert calculate_wages(days, rate, advance, payments)["outstanding"] == outstanding


def test_demo_breakdown():
    r = calculate_wages(6, 700, 500, 3000)
    assert (r["expected"], r["received"]) == (4200, 3500)
    assert [line["amount"] for line in r["breakdown"]] == ["₹4,200", "− ₹500", "− ₹3,000", "₹700"]


def test_never_negative():
    r = calculate_wages(2, 500, 1000, 500)
    assert (r["outstanding"], r["overpaid"]) == (0, 500)


@pytest.mark.parametrize("bad", [(-1, 700, 0, 0), (6, "700", 0, 0), (6, 700.5, 0, 0), (True, 700, 0, 0)])
def test_rejects_bad_input(bad):
    with pytest.raises((TypeError, ValueError)):
        calculate_wages(*bad)


def test_inr_grouping():
    assert format_inr(4200) == "₹4,200"
    assert format_inr(125000) == "₹1,25,000"


def test_message_uses_python_numbers():
    msg = payment_request(calculate_wages(6, 700, 500, 3000))
    for s in ["6 din × ₹700 = ₹4,200", "₹500", "₹3,000", "₹3,500", "Baaki: ₹700"]:
        assert s in msg
