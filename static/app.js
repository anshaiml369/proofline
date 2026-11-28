// PagarSaathi front end.
// Voice IN is Wispr Flow: the worker dictates into the text box (double-tap Fn on Mac, the
// Wispr Flow keyboard on iPhone). This page has no microphone code by design.
// Voice OUT is Sarvam Bulbul (natural Hindi) when the server has a key, or a pre-recorded clip;
// otherwise the browser's own SpeechSynthesis (free). No arithmetic happens here: every number on the
// card comes from the server (wage_math.py).
(() => {
  const params = new URLSearchParams(location.search);
  const scripted = params.get('mode') === 'scripted';
  const textMode = params.get('mode') === 'text';
  const debug = params.get('debug') === '1';
  const dlog = (...a) => { if (debug) console.log('[PagarSaathi]', new Date().toISOString().slice(11, 23), ...a); };

  // The demo conversation: what the worker says (via Wispr Flow) at each turn.
  const SCRIPT = [
    'Mujhe thekedar ne is hafte poore paise nahi diye.',
    'Chhe din.',
    'Saat sau rupaye.',
    'Paanch sau.',
    'Teen hazaar.',
    'Haan.',
    'Haan.',
  ];

  const $ = (id) => document.getElementById(id);
  const el = {
    agent: $('agent-text'), speaking: $('speaking'), replay: $('replay'), start: $('start'),
    form: $('answer-form'), answer: $('answer'), cont: $('continue'), status: $('status'), assist: $('assist'),
    result: $('result'), calc: $('calc'), nodue: $('nodue'), previewWrap: $('preview-wrap'),
    preview: $('preview'), send: $('send'), again: $('again'), log: $('log'), chip: $('mode-chip'),
    keyless: $('keyless'),
  };
  const show = (node, on = true) => node.classList.toggle('hidden', !on);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const inr = (n) => '₹' + Number(n).toLocaleString('en-IN');

  let sessionId = null;
  let last = null;            // last server reply (for replay)
  let busy = false;
  let message = '';
  let scriptStopped = false;
  const player = new Audio();
  const played = new Set();      // "state|url": a clip never plays twice in the same state
  // Debug: every media event, so a stray or repeated clip shows up in the console (?debug=1).
  for (const ev of ['play', 'pause', 'ended', 'error']) {
    player.addEventListener(ev, () => dlog('audio', ev, player.currentSrc.split('/').pop(),
      ev === 'error' && player.error ? 'code ' + player.error.code : ''));
  }
  // A 0.1 s silent WAV, played inside the Start tap so later clips are allowed to play (Safari/iOS).
  const SILENT = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';

  // ---------- voice out ----------
  let voices = [];
  const loadVoices = () => { voices = window.speechSynthesis ? speechSynthesis.getVoices() : []; };
  loadVoices();
  if (window.speechSynthesis) speechSynthesis.onvoiceschanged = loadVoices;
  const hindiVoice = () => voices.find((v) => /^hi(-|_|$)/i.test(v.lang));

  function stopSpeaking() {
    if (window.speechSynthesis) speechSynthesis.cancel();
    player.pause();
  }

  function utter(text, voice, lang) {
    return new Promise((resolve) => {
      dlog('browser voice', lang, voice ? voice.name : '(default)', JSON.stringify(text));
      const u = new SpeechSynthesisUtterance(text);
      if (voice) u.voice = voice;
      u.lang = lang;
      u.rate = 0.95;
      // Some browsers never fire onend: cap the wait by text length.
      const guard = setTimeout(resolve, 1500 + text.length * 90);
      u.onend = u.onerror = () => { clearTimeout(guard); resolve(); };
      speechSynthesis.speak(u);
    });
  }

  // Resolves true when the clip played to the end (or was cut off on purpose), false if it could
  // not play at all, so the caller can fall back to the browser voice instead of staying silent.
  function playClip(url) {
    return new Promise((resolve) => {
      let started = false;
      const finish = (ok) => { player.onended = player.onerror = player.onpause = player.onplaying = null; resolve(ok); };
      player.onplaying = () => { started = true; };
      player.onended = () => finish(true);
      player.onpause = () => finish(started);
      player.onerror = () => finish(false);
      player.src = url;
      player.play().catch((e) => { dlog('audio play() rejected', e.name); finish(false); });
    });
  }

  // Returns which voice actually spoke: "recorded", "sarvam", "browser" or "none".
  async function speak(reply, { force = false } = {}) {
    stopSpeaking();
    const key = reply.state + '|' + (reply.agent_audio_url || reply.agent_text);
    if (!force && played.has(key)) { dlog('skip repeat', key); return 'none'; }
    played.add(key);
    show(el.speaking, true);
    // Browser voices can read "?" aloud as "question mark": speak a danda instead.
    const clean = (t) => t.replace(/\s*[?？]+/g, '।').replace(/।\s*।/g, '।');
    try {
      if (reply.agent_audio_url && await playClip(reply.agent_audio_url)) return reply.audio_source || 'recorded';
      const hi = window.speechSynthesis && hindiVoice();
      if (hi) { await utter(clean(reply.speak_text), hi, 'hi-IN'); return 'browser'; }
      if (window.speechSynthesis && voices.length) { await utter(clean(reply.agent_text), null, 'en-IN'); return 'browser'; }
      await sleep(Math.min(3500, 600 + reply.agent_text.length * 30));       // no voice at all: reading time
      return 'none';
    } finally {
      show(el.speaking, false);
    }
  }

  // ---------- rendering ----------
  function setStatus(text, isError = false) {
    el.status.textContent = text || '';
    el.status.className = 'mt-3 min-h-[1.5rem] text-base ' + (isError ? 'font-semibold text-rose-300' : 'text-slate-400');
  }

  const TEXT_LABEL = { llm: 'Text: LLM', rules: 'Text: Rules' };
  const VOICE_LABEL = { recorded: 'Voice: Recorded', sarvam: 'Voice: Sarvam', browser: 'Voice: Browser', none: 'Voice: off' };
  const INPUT_LABEL = { typed: 'Wispr Flow / typed', scripted: 'Scripted demo' };

  // Small grey provenance line under a bubble: where this line came from.
  function badge(li, text) {
    const b = document.createElement('li');
    b.setAttribute('role', 'note');
    b.className = 'prov mt-1 text-[11px] font-medium tracking-wide ' + (li.classList.contains('self-end') ? 'text-right text-indigo-300/80' : 'text-slate-400');
    b.textContent = text;
    li.after(b);
    b.classList.add(li.classList.contains('self-end') ? 'self-end' : 'self-start');
    return b;
  }

  function bubble(text, who, tag) {
    const empty = el.log.querySelector('.empty');
    if (empty) empty.remove();
    const li = document.createElement('li');
    li.className = who === 'agent'
      ? 'max-w-[85%] self-start rounded-2xl rounded-bl-md bg-slate-700/60 px-4 py-2.5 text-[17px] leading-snug text-slate-100'
      : 'max-w-[85%] self-end rounded-2xl rounded-br-md bg-indigo-500 px-4 py-2.5 text-[17px] leading-snug text-white';
    li.textContent = text;
    if (tag) {
      const t = document.createElement('span');
      t.className = 'ml-2 rounded-full bg-white/20 px-2 py-0.5 text-xs font-bold';
      t.textContent = tag;
      li.append(t);
    }
    el.log.append(li);
    return li;
  }

  function showFact(parsed) {
    const box = parsed && document.querySelector(`.fact[data-field="${parsed.field}"]`);
    if (!box) return;
    box.classList.add('border-emerald-400/40', 'bg-emerald-400/10');
    const b = box.querySelector('b');
    b.className = 'mt-0.5 block text-base font-bold text-white';
    b.textContent = (parsed.field === 'days' ? parsed.value : inr(parsed.value)) + (parsed.assumed ? '?' : '');
  }

  function showFacts(facts) {      // the LLM can hear several facts in one sentence
    if (!facts) return;
    clearFacts();
    for (const [field, value] of Object.entries(facts)) showFact({ field, value });
  }

  function clearFacts() {
    document.querySelectorAll('.fact').forEach((box) => {
      box.classList.remove('border-emerald-400/40', 'bg-emerald-400/10');
      const b = box.querySelector('b');
      b.className = 'mt-0.5 block text-base text-slate-500';
      b.textContent = '—';
    });
  }

  function factTag(parsed) {
    if (!parsed) return null;
    return (parsed.field === 'days' ? `${parsed.value} din` : inr(parsed.value)) + (parsed.assumed ? ' (maana)' : '');
  }

  function renderCase(c) {
    el.calc.replaceChildren();
    for (const line of c.breakdown) {
      const row = document.createElement('div');
      row.className = 'flex items-baseline justify-between gap-4 py-3.5';
      const left = document.createElement('div');
      left.className = line.total ? 'text-2xl font-extrabold text-white' : 'text-[17px] text-slate-200';
      left.textContent = line.label;
      if (line.math && line.math !== 'minus') {
        const s = document.createElement('div');
        s.className = 'text-sm font-normal text-slate-400';
        s.textContent = line.math;
        left.append(s);
      }
      const amt = document.createElement('div');
      amt.className = 'whitespace-nowrap font-semibold tabular-nums ' +
        (line.total ? (c.outstanding > 0 ? 'text-2xl font-extrabold text-amber-300' : 'text-2xl font-extrabold text-emerald-300') : 'text-[17px] text-slate-100');
      amt.textContent = line.amount;
      row.append(left, amt);
      el.calc.append(row);
    }
    show(el.nodue, c.outstanding <= 0);
    show(el.result, true);
  }

  // ---------- server ----------
  async function post(body) {
    const resp = await fetch('/turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, session_id: sessionId, mode: scripted ? 'scripted' : '' }),
    });
    let data = {};
    try { data = await resp.json(); } catch { /* non-JSON error page */ }
    if (!resp.ok && !data.error) data.error = 'Server se jawab nahi aaya. Phir se koshish kijiye.';
    return data;
  }

  async function handle(data, saidText) {
    if (data.error) { setStatus(data.error, true); return false; }
    sessionId = data.session_id;
    if (saidText !== undefined) badge(bubble(saidText, 'worker', factTag(data.parsed)), INPUT_LABEL[data.input_source] || 'Typed');
    if (data.state === 'ASK_DAYS' && saidText !== undefined && last && last.state === 'CONFIRM') clearFacts();
    if (data.facts) showFacts(data.facts); else showFact(data.parsed);
    if (data.parsed && data.parsed.assumed) showFact(data.parsed);

    last = data;
    el.agent.textContent = data.agent_text;
    const prov = badge(bubble(data.agent_text, 'agent'), TEXT_LABEL[data.text_source] || 'Text: Rules');
    dlog('reply', data.state, data.text_source, data.audio_source, JSON.stringify(data.agent_text));
    show(el.replay, true);
    show(el.assist, !!data.needs_assistance && !data.case_data);
    setStatus('');
    if (data.case_data) renderCase(data.case_data);

    const finished = data.done;
    const preview = data.state === 'SHOW_PREVIEW' && data.case_data && data.case_data.payment_request;
    if (finished || preview) show(el.form, false);
    if (finished) show(el.again, true);
    if (!finished && !preview && !scripted) el.answer.focus();   // Wispr Flow types into the focused field

    const spoken = speak(data).then((voice) => { prov.textContent += ' · ' + VOICE_LABEL[voice]; });
    if (preview) {
      // SHOW_PREVIEW: the message appears first, the Send button after it.
      message = data.case_data.payment_request;
      el.preview.textContent = message;
      show(el.previewWrap, true);
      el.previewWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
      await sleep(1200);
      el.send.classList.remove('hidden');
      el.send.classList.add('flex');
    }
    await spoken;
    return true;
  }

  let queued = false;
  async function submit(text) {
    if (scriptStopped && scripted) return;
    if (!text) { setStatus('Pehle jawab boliye (Wispr Flow) ya likhiye, phir Continue dabaiye.'); el.answer.focus(); return; }
    if (busy) { queued = true; setStatus('Ek second…'); return; }   // sent when the current reply arrives
    busy = true;
    el.cont.disabled = true;
    stopSpeaking();
    setStatus('Samajh raha hoon…');
    try {
      const data = await post({ text });
      // Clear only what was sent: anything dictated meanwhile stays in the box.
      if (!data.error && el.answer.value.trim() === text) el.answer.value = '';
      busy = false;
      el.cont.disabled = false;
      const handled = handle(data, data.error ? undefined : text);
      if (queued) { queued = false; const next = el.answer.value.trim(); if (next) await submit(next); }
      await handled;
    } catch {
      setStatus('Server se connection nahi hua. Phir se koshish kijiye.', true);
    } finally {
      busy = false;
      el.cont.disabled = false;
    }
  }

  // ---------- scripted demo: fills the box as Wispr Flow would, presses Continue ----------
  async function runScript() {
    for (const line of SCRIPT) {
      await sleep(900);
      el.answer.focus();
      for (let i = 1; i <= line.length; i++) {           // text "appears" like dictation
        el.answer.value = line.slice(0, i);
        await sleep(18);
      }
      await sleep(1100);
      el.cont.classList.add('ring-4', 'ring-indigo-300/60');
      await sleep(250);
      el.cont.classList.remove('ring-4', 'ring-indigo-300/60');
      await submit(el.answer.value.trim());
      if (last && (last.state === 'SHOW_PREVIEW' || last.done)) break;   // stop cleanly: never type past the end
    }
    scriptStopped = true;
    dlog('script finished at', last && last.state);
  }

  // ---------- wiring ----------
  el.start.addEventListener('click', async () => {
    show(el.start, false);
    // Unlock the audio element inside this tap, so later clips may play without one.
    player.src = SILENT;
    player.play().then(() => { if (player.src === SILENT) player.pause(); }).catch(() => {});
    // Unlock speech on this tap (browsers need a user gesture before talking).
    if (window.speechSynthesis) speechSynthesis.speak(new SpeechSynthesisUtterance(''));
    show(el.form, true);
    show($('wispr-hint'), false);   // the answer box carries the Wispr Flow label from here on
    setStatus('Shuru ho raha hai…');
    try {
      const ok = await handle(await post({}));
      if (ok && scripted) runScript();
    } catch {
      show(el.start, true);
      setStatus('Server se connection nahi hua.', true);
    }
  });

  el.form.addEventListener('submit', (e) => { e.preventDefault(); submit(el.answer.value.trim()); });
  el.answer.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(el.answer.value.trim()); }
  });
  el.answer.addEventListener('input', () => { if (el.answer.value) stopSpeaking(); });
  el.replay.addEventListener('click', () => last && speak(last, { force: true }));

  el.send.addEventListener('click', async () => {
    // Plain deep link, no WhatsApp API: the worker picks the contractor's chat and presses send.
    window.open('https://wa.me/?text=' + encodeURIComponent(message), '_blank', 'noopener');
    try {
      const data = await post({ event: 'sent' });
      if (!data.error) {
        last = data;
        el.agent.textContent = data.agent_text;
        const prov = badge(bubble(data.agent_text, 'agent'), TEXT_LABEL[data.text_source] || 'Text: Rules');
        show(el.again, true);
        speak(data).then((voice) => { prov.textContent += ' · ' + VOICE_LABEL[voice]; });
      }
    } catch { /* WhatsApp already opened */ }
  });

  el.again.addEventListener('click', () => location.reload());
  if (scripted) show(el.chip, true);
  if (textMode) { el.chip.textContent = 'Text mode'; show(el.chip, true); }

  // Tell a judge up front when the server runs without keys (rules + recorded voice).
  fetch('/health').then((r) => r.json()).then((h) => {
    dlog('health', JSON.stringify(h));
    if (h.mode === 'keyless' && !scripted) {
      el.keyless.textContent = 'Demo mode: built-in rules + recorded voice. LLM aur Sarvam voice ke liye server par ' +
        h.missing.join(' aur ') + ' set kijiye.';
      show(el.keyless, true);
    }
  }).catch(() => {});
})();
