// PagarSaathi front end.
// Voice IN is Wispr Flow: the worker dictates into the text box (double-tap Fn on Mac, the
// Wispr Flow keyboard on iPhone). This page has no microphone code by design.
// Voice OUT is the browser's own SpeechSynthesis (free). A pre-recorded / Sarvam clip is used
// only when the browser has no Hindi voice. No arithmetic happens here: every number on the
// card comes from the server (wage_math.py).
(() => {
  const scripted = new URLSearchParams(location.search).get('mode') === 'scripted';

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
  };
  const show = (node, on = true) => node.classList.toggle('hidden', !on);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const inr = (n) => '₹' + Number(n).toLocaleString('en-IN');

  let sessionId = null;
  let last = null;            // last server reply (for replay)
  let busy = false;
  let message = '';
  const player = new Audio();

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

  function playClip(url) {
    return new Promise((resolve) => {
      const done = () => { player.onended = player.onerror = player.onpause = null; resolve(); };
      player.onended = player.onerror = player.onpause = done;
      player.src = url;
      player.play().catch(done);
    });
  }

  async function speak(reply) {
    stopSpeaking();
    show(el.speaking, true);
    try {
      const hi = window.speechSynthesis && hindiVoice();
      if (hi) return await utter(reply.speak_text, hi, 'hi-IN');            // primary: free browser voice
      if (reply.agent_audio_url) return await playClip(reply.agent_audio_url); // fallback: recorded / Sarvam
      if (window.speechSynthesis && voices.length) return await utter(reply.agent_text, null, 'en-IN');
      await sleep(Math.min(3500, 600 + reply.agent_text.length * 30));       // no voice at all: reading time
    } finally {
      show(el.speaking, false);
    }
  }

  // ---------- rendering ----------
  function setStatus(text, isError = false) {
    el.status.textContent = text || '';
    el.status.className = 'mt-3 min-h-[1.5rem] text-base ' + (isError ? 'font-semibold text-rose-300' : 'text-slate-400');
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
  }

  function showFact(parsed) {
    const box = parsed && document.querySelector(`.fact[data-field="${parsed.field}"]`);
    if (!box) return;
    box.classList.add('border-emerald-400/40', 'bg-emerald-400/10');
    const b = box.querySelector('b');
    b.className = 'mt-0.5 block text-base font-bold text-white';
    b.textContent = (parsed.field === 'days' ? parsed.value : inr(parsed.value)) + (parsed.assumed ? '?' : '');
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
    if (saidText !== undefined) bubble(saidText, 'worker', factTag(data.parsed));
    if (data.state === 'ASK_DAYS' && saidText !== undefined && last && last.state === 'CONFIRM') clearFacts();
    showFact(data.parsed);

    last = data;
    el.agent.textContent = data.agent_text;
    bubble(data.agent_text, 'agent');
    show(el.replay, true);
    show(el.assist, !!data.needs_assistance && !data.case_data);
    setStatus('');
    if (data.case_data) renderCase(data.case_data);

    const finished = data.done;
    const preview = data.state === 'SHOW_PREVIEW' && data.case_data && data.case_data.payment_request;
    if (finished || preview) show(el.form, false);
    if (finished) show(el.again, true);
    if (!finished && !preview && !scripted) el.answer.focus();   // Wispr Flow types into the focused field

    const spoken = speak(data);
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
    if (!text) return;
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
      if (!el.send.classList.contains('hidden') || (last && last.done)) break;
    }
  }

  // ---------- wiring ----------
  el.start.addEventListener('click', async () => {
    show(el.start, false);
    // Unlock speech on this tap (browsers need a user gesture before talking).
    if (window.speechSynthesis) speechSynthesis.speak(new SpeechSynthesisUtterance(''));
    show(el.form, true);
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
  el.replay.addEventListener('click', () => last && speak(last));

  el.send.addEventListener('click', async () => {
    // Plain deep link, no WhatsApp API: the worker picks the contractor's chat and presses send.
    window.open('https://wa.me/?text=' + encodeURIComponent(message), '_blank', 'noopener');
    try {
      const data = await post({ event: 'sent' });
      if (!data.error) {
        last = data;
        el.agent.textContent = data.agent_text;
        bubble(data.agent_text, 'agent');
        show(el.again, true);
        speak(data);
      }
    } catch { /* WhatsApp already opened */ }
  });

  el.again.addEventListener('click', () => location.reload());
  if (scripted) show(el.chip, true);
})();
