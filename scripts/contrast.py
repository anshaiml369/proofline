"""WCAG contrast of every text/background pair the page uses (DESIGN.md tokens).

    python3 scripts/contrast.py      # prints a table; exits 1 if any text pair fails AA

Large text (24 px+, or 18.66 px+ bold) needs 3:1; everything else 4.5:1. Non-text pairs
(ember underline, borders) are listed for information and need 3:1 (WCAG 1.4.11).
"""
import sys

CANVAS, INK, LAV, LAV_H = "#ffffeb", "#1a1a1a", "#f0d7ff", "#e6c4ff"
TEAL, EMBER, EMBER_INK, MUTED, WHITE = "#034f46", "#ffa946", "#8a4b00", "#555555", "#ffffff"
GLASS = ("#ffffeb", 0.72)          # rgba(255,255,235,0.72) over the cream page


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def blend(fg_hex, alpha, bg_hex):
    f, b = rgb(fg_hex), rgb(bg_hex)
    return "#" + "".join(f"{round(alpha * x + (1 - alpha) * y):02x}" for x, y in zip(f, b))


def lum(h):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


GLASS_BG = blend(GLASS[0], GLASS[1], CANVAS)

# (where it is used, text colour, background, large text?)
TEXT_PAIRS = [
    ("Body, h1, ₹ amount on the page and card", INK, CANVAS, False),
    ("Lavender buttons (Bolo, Continue, Send)", INK, LAV, False),
    ("Lavender button hover", INK, LAV_H, False),
    ("Worker bubble", INK, LAV, False),
    ("Agent bubble / log on glass", INK, GLASS_BG, False),
    ("Provenance line on glass", MUTED, GLASS_BG, False),
    ("Helper text, captions, fact labels", MUTED, CANVAS, False),
    ("Teal: Escalate, notes, sent-at, speaking tag", TEAL, CANVAS, False),
    ("Confirmed chip (cream on teal)", CANVAS, TEAL, False),
    ("Error line (ember-ink)", EMBER_INK, CANVAS, False),
    ("Scripted chip (cream on ink)", CANVAS, INK, False),
    ("Textarea, preview, draft (ink on white)", INK, WHITE, False),
    ("Placeholder (muted on white)", MUTED, WHITE, False),
    ("Toast on glass (teal)", TEAL, GLASS_BG, False),
    ("Fact chip filled (teal tint)", INK, blend(TEAL, 0.08, CANVAS), False),
    ("Escalate hover (teal on teal tint)", TEAL, blend(TEAL, 0.08, CANVAS), False),
    ("Log-empty / logo tile ₹ (ink on lavender)", INK, LAV, True),
]
NON_TEXT = [
    ("Ember underline under ₹ (decoration)", EMBER, CANVAS),
    ("Ink 2 px borders", INK, CANVAS),
    ("Teal focus ring", TEAL, CANVAS),
]


def main():
    fails = 0
    print(f"{'Pair':48} {'fg':8} {'bg':8} {'ratio':>6}  AA")
    for name, fg, bg, large in TEXT_PAIRS:
        r = ratio(fg, bg)
        ok = r >= (3 if large else 4.5)
        fails += not ok
        print(f"{name:48} {fg:8} {bg:8} {r:6.2f}  {'pass' if ok else 'FAIL'}")
    print("\nNon-text (3:1, WCAG 1.4.11):")
    for name, fg, bg in NON_TEXT:
        r = ratio(fg, bg)
        print(f"{name:48} {fg:8} {bg:8} {r:6.2f}  {'pass' if r >= 3 else 'info: decorative, the amount itself is ink'}")
    print(f"\nText pairs failing AA: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
