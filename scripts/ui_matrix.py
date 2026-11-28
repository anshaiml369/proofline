"""UI test matrix U1-U9 for the redesigned page, with screenshots in screenshots/.

Dev-only (needs Playwright, not in requirements.txt):
    pip install playwright && python -m playwright install chromium
    OPENAI_API_KEY= OPENROUTER_API_KEY= SARVAM_API_KEY= PORT=5071 python3 app.py   # a keyless server
    python scripts/ui_matrix.py http://localhost:5071

Prints one PASS/FAIL line per test with the measured values, and writes:
    screenshots/U1..U9*.png, screenshots/U5_side_by_side.png (with the mockup),
    screenshots/scripted_10s.mp4 (10 s around the card entrance and count-up).
"""
import json
import pathlib
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5071").rstrip("/")
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)
MOCKUP = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
PHONE = {"width": 390, "height": 844}
results = []


def record(name, ok, detail):
    results.append((name, ok, detail))
    print(f"{name:4} {'PASS' if ok else 'FAIL'}  {detail}")


def rect(page, sel):
    return page.eval_on_selector(sel, "e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height, b: r.bottom, r: r.right}; }")


# Every visible text element: its colour against the first opaque background behind it.
CONTRAST_JS = r"""
() => {
  const parse = (c) => { const m = c.match(/[\d.]+/g); return m ? m.map(Number) : [0,0,0,0]; };
  const lum = ([r,g,b]) => { const f = (c) => { c/=255; return c <= 0.03928 ? c/12.92 : ((c+0.055)/1.055)**2.4; };
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
  const over = (top, under) => { const a = top[3] === undefined ? 1 : top[3];
    return [0,1,2].map(i => a*top[i] + (1-a)*under[i]); };
  function bgOf(el) {
    const stack = [];
    for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c.length === 3) c.push(1);
      if (c[3] > 0) { stack.push(c); if (c[3] >= 1) break; }
    }
    let col = [255,255,255];
    for (let i = stack.length - 1; i >= 0; i--) col = over(stack[i], col);
    return col;
  }
  const fails = []; let checked = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (!['P','SPAN','H1','H2','H3','B','DT','DD','SMALL','LI','BUTTON','A','LABEL','PRE','SELECT','TEXTAREA','DIV'].includes(el.tagName)) continue;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (!r.width || !r.height || cs.visibility === 'hidden' || el.closest('.hidden')) continue;
    let op = 1; for (let n = el; n; n = n.parentElement) op *= Number(getComputedStyle(n).opacity);
    if (op < 0.99) continue;                         // disabled controls (50%) are exempt in WCAG
    const fg = parse(cs.color); const bg = bgOf(el);
    const fgc = over(fg.length === 4 ? fg : [...fg, 1], bg);
    const L1 = lum(fgc), L2 = lum(bg); const ratio = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    const size = parseFloat(cs.fontSize); const bold = Number(cs.fontWeight) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5;
    checked++;
    if (ratio < need) fails.push({text: el.textContent.trim().slice(0, 40), ratio: +ratio.toFixed(2), need, size});
    if (size < 14) fails.push({text: el.textContent.trim().slice(0, 40), tooSmall: size});
  }
  return {checked, fails};
}
"""


def run_script_to_preview(page, timeout_s=120):
    page.click("#bolo")
    t0 = time.time()
    page.wait_for_selector("#send:not(.hidden)", timeout=timeout_s * 1000)
    return time.time() - t0


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])

    # ---------- U1 + U8: 390 px, no keys ----------
    ctx = browser.new_context(viewport=PHONE, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(BASE + "/")
    page.wait_for_selector("#keyless:not(.hidden)", timeout=10000)
    page.wait_for_timeout(900)
    h1, bolo, kl = rect(page, "#agent-text"), rect(page, "#bolo"), rect(page, "#keyless")
    # layout size, not the box mid-pulse (the idle pulse scales it to 1.03)
    bolo["w"], bolo["h"] = page.eval_on_selector("#bolo", "e => [e.offsetWidth, e.offsetHeight]")
    sw = page.evaluate("document.documentElement.scrollWidth")
    health = page.evaluate("fetch('/health').then(r => r.json())")
    page.screenshot(path=str(OUT / "U1_390_keyless.png"))
    ok = (h1["y"] >= 0 and h1["b"] <= PHONE["height"] and round(bolo["w"]) == 160 and round(bolo["h"]) == 160
          and kl["h"] > 0 and sw <= 390 and health.get("mode") == "keyless")
    record("U1", ok, f"h1 {h1['y']:.0f}-{h1['b']:.0f}px of 844, Bolo {bolo['w']:.0f}x{bolo['h']:.0f}, keyless chip shown, "
                     f"/health mode={health.get('mode')}, scrollWidth {sw}")
    overlap = not (kl["b"] <= bolo["y"] or kl["y"] >= bolo["b"] or kl["r"] <= bolo["x"] or kl["x"] >= bolo["r"])
    record("U8", not overlap, f"keyless chip y {kl['y']:.0f}-{kl['b']:.0f}, Bolo y {bolo['y']:.0f}-{bolo['b']:.0f}: "
                              f"{'overlap' if overlap else 'no overlap'}")
    ctx.close()

    # ---------- U2: 1440 px ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/")
    page.wait_for_timeout(900)
    m = rect(page, "main")
    page.screenshot(path=str(OUT / "U2_1440.png"))
    record("U2", round(m["w"]) == 560 and abs(m["x"] - (1440 - 560) / 2) < 1,
           f"main width {m['w']:.0f}px at x={m['x']:.0f} (centre would be {(1440 - 560) / 2:.0f})")
    ctx.close()

    # ---------- scripted run with video: U3, U5, U6, U7, motion evidence ----------
    vid_dir = OUT / "_video"
    ctx = browser.new_context(viewport=PHONE, device_scale_factor=1, record_video_dir=str(vid_dir), record_video_size=PHONE)
    page = ctx.new_page()
    t_page = time.time()
    page.goto(BASE + "/?mode=scripted")
    # count how often the amount restarts at ₹0 (count-up runs) and the card's spring entrances
    page.evaluate("""() => {
      window.__ups = 0; window.__amounts = [];
      new MutationObserver(() => { const v = document.getElementById('outstanding').textContent;
        if (v === '₹0') window.__ups++; window.__amounts.push(v); })
        .observe(document.getElementById('outstanding'), {childList: true, characterData: true, subtree: true});
      window.__entr = 0;
      new MutationObserver(() => { const s = document.getElementById('result').style.transform || '';
        if (/scale\\(0\\.9[6-9]/.test(s) || /translateY\\(2[0-4]/.test(s)) window.__entr_seen = (window.__entr_seen||0) + 1;
        if (!document.getElementById('result').classList.contains('hidden') && !window.__shown) { window.__shown = true; window.__entr++; window.__shown_at = performance.now(); } })
        .observe(document.getElementById('result'), {attributes: true});
    }""")
    t_click = time.time()
    run_script_to_preview(page)
    shown_at = page.evaluate("window.__shown_at") / 1000.0          # seconds since navigation start
    page.wait_for_timeout(800)
    ups, amounts = page.evaluate("[window.__ups, window.__amounts.slice(0, 6).concat(['…'], window.__amounts.slice(-1))]")
    record("M1", ups == 1, f"count-up ran {ups} time(s); first values {amounts}")

    # U3: computed contrast + minimum sizes of every visible text element in the finished state
    c = page.evaluate(CONTRAST_JS)
    record("U3", not c["fails"], f"{c['checked']} visible text elements checked, {len(c['fails'])} failures "
                                 f"{c['fails'][:3] if c['fails'] else ''}")

    # U5: the card as the worker sees it
    page.evaluate("window.scrollTo(0, document.getElementById('result').offsetTop - document.getElementById('q').offsetHeight - 8)")
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / "U5_scripted_card.png"))

    # U6: turn log after the whole run
    log = page.evaluate("""() => { const l = document.getElementById('log'); const items = l.querySelectorAll('li.msg');
      const last = l.lastElementChild.getBoundingClientRect(); const box = l.getBoundingClientRect();
      return {turns: items.length, scrollable: l.scrollHeight > l.clientHeight, sh: l.scrollHeight, ch: l.clientHeight,
              lastVisible: last.bottom <= box.bottom + 1 && last.top >= box.top - 1}; }""")
    page.eval_on_selector("#log", "e => e.scrollIntoView({block: 'end'})")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "U6_turn_log.png"))
    record("U6", log["turns"] >= 6 and log["scrollable"] and log["lastVisible"],
           f"{log['turns']} bubbles, scrollHeight {log['sh']} > clientHeight {log['ch']}, latest line visible: {log['lastVisible']}")

    # U7: Send -> WhatsApp tab opens -> "Bheja gaya: <time>"
    with ctx.expect_page() as popup:
        page.click("#send")
    wa = popup.value
    wa_url = wa.url
    wa.close()
    page.wait_for_selector("#sent-at:not(.hidden)", timeout=10000)
    sent, toast = page.inner_text("#sent-at"), page.inner_text("#toast")
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / "U7_sent.png"))
    record("U7", "Bheja gaya" in sent and any(ch.isdigit() for ch in sent),
           f"opened {wa_url[:30]}…; card: '{sent}'; glass toast: '{toast.strip()}'")
    ups_after = page.evaluate("window.__ups")
    record("M2", ups_after == 1 and page.evaluate("window.__entr") == 1,
           f"after Send: count-up runs {ups_after}, card entrances {page.evaluate('window.__entr')}")
    video_path = page.video.path()
    ctx.close()

    # 10 s clip around the entrance: starts 4 s before the card appears
    start = max(0.0, shown_at - 4.0)
    clip = OUT / "scripted_10s.mp4"
    ff = shutil.which("ffmpeg")
    if ff:
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(video_path), "-t", "10",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(clip)], check=True)
        probe = subprocess.run([ff, "-i", str(clip)], capture_output=True, text=True).stderr
        dur = next((ln.split("Duration:")[1].split(",")[0].strip() for ln in probe.splitlines() if "Duration:" in ln), "?")
        record("M3", clip.exists(), f"{clip.name}: {dur}, from {start:.1f}s of the run (card appears at {shown_at:.1f}s)")
        # a few frames across the entrance, as stills
        for i, dt in enumerate((0.0, 0.15, 0.3, 0.6)):
            subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{shown_at + dt:.2f}", "-i", str(video_path),
                            "-frames:v", "1", str(OUT / f"M_entrance_{i}_{int(dt * 1000)}ms.png")], check=True)
    shutil.rmtree(vid_dir, ignore_errors=True)

    # ---------- U4: reduced motion ----------
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(BASE + "/?mode=scripted")
    page.evaluate("""() => { window.__vals = []; window.__tf = new Set();
      new MutationObserver(() => window.__vals.push(document.getElementById('outstanding').textContent))
        .observe(document.getElementById('outstanding'), {childList: true, characterData: true, subtree: true});
      for (const id of ['result', 'agent-text', 'bolo', 'preview-wrap']) new MutationObserver(() => {
        const s = document.getElementById(id).style.transform; if (s && s !== 'none') window.__tf.add(id + ':' + s); })
        .observe(document.getElementById(id), {attributes: true, attributeFilter: ['style']}); }""")
    bolo_anim = page.eval_on_selector("#bolo", "e => getComputedStyle(e).animationName")
    run_script_to_preview(page)
    page.wait_for_timeout(500)
    vals, tf = page.evaluate("[window.__vals, [...window.__tf]]")
    page.screenshot(path=str(OUT / "U4_reduced_motion.png"))
    record("U4", bolo_anim == "none" and "₹0" not in vals and not tf,
           f"Bolo animation '{bolo_anim}'; amount values {vals}; inline transforms seen: {tf or 'none'}")
    ctx.close()

    # ---------- U9: backend 503 ----------
    ctx = browser.new_context(viewport=PHONE)
    page = ctx.new_page()
    page.route("**/turn", lambda route: route.fulfill(status=503, content_type="text/html",
               body="<html><body><h1>503 Service Unavailable</h1><pre>Traceback (most recent call last): ...</pre></body></html>"))
    page.goto(BASE + "/")
    page.click("#bolo")
    page.wait_for_selector("#error:not(.hidden)", timeout=10000)
    page.wait_for_timeout(500)
    err = page.inner_text("#error")
    page.screenshot(path=str(OUT / "U9_backend_503.png"))
    bad = [s for s in ("{", "Traceback", "<", "503", "Service Unavailable") if s in err]
    color = page.eval_on_selector("#error", "e => getComputedStyle(e).color")
    record("U9", not bad and "Sun nahi paya" in err, f"shown: '{err}' (colour {color}); raw markers found: {bad or 'none'}")
    ctx.close()

    # ---------- U5 side by side with the mockup ----------
    if MOCKUP and MOCKUP.exists():
        ctx = browser.new_context(viewport=PHONE, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(MOCKUP.as_uri())
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "U5_mockup.png"))
        ctx.close()
        if shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT / "U5_mockup.png"), "-i", str(OUT / "U5_scripted_card.png"),
                            "-filter_complex", "[0:v]pad=iw+24:ih:0:0:color=0xffffeb[a];[a][1:v]hstack=inputs=2",
                            str(OUT / "U5_side_by_side.png")], check=True)
        record("U5", (OUT / "U5_side_by_side.png").exists(), "mockup (left) vs scripted card (right): U5_side_by_side.png")
    browser.close()

print()
fails = [n for n, ok, _ in results if not ok]
print(json.dumps({"passed": len(results) - len(fails), "failed": fails}))
sys.exit(1 if fails else 0)
