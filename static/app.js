// PagarSaathi front end: record → POST /turn → show + speak the agent's reply.
// No arithmetic happens here: every number on the card comes from the server (wage_math.py).
(() => {
  const cfg = window.PAGAR || {};
  const params = new URLSearchParams(location.search);
  let mode = ['text', 'scripted'].includes(params.get('mode')) ? params.get('mode') : 'voice';
  if (mode === 'voice' && cfg.voiceOk === false) mode = 'text';   // no speech-to-text key: type instead
  const MAX_RECORD_MS = 12000;

  // The exact demo conversation (worker side). Agent lines come from the server's state machine.
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
    agent: $('agent-text'), replay: $('replay'), start: $('start'), mic: $('mic'), typed: $('typed'),
    input: $('typed-input'), status: $('status'), sw: $('switch'), log: $('log'), result: $('result'),
    calc: $('calc'), nodue: $('nodue'), previewWrap: $('preview-wrap'), preview: $('preview'),
    send: $('send'), again: $('again'), chip: $('mode-chip'),
  };

  let sessionId = null;
  let lastQuestion = '';
  let lastAudio = null;
  let busy = false;
  let finished = false;
  let message = '';
  const player = new Audio();

  // ---------- helpers ----------
  const inr = (n) => '₹' + Number(n).toLocaleString('en-IN');
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function setStatus(text, isError = false) {
    el.status.textContent = text || '';
    el.status.classList.toggle('error', !!isError);
  }

  function setBusy(on, label) {
    busy = on;
    el.mic.classList.toggle('busy', on);
    el.mic.disabled = on || finished;
    el.typed.querySelector('button').disabled = on || finished;
    if (label !== undefined) setStatus(label);
  }

  function play(url, text) {
    // Resolves when the clip ends. No clip (TTS failed / not recorded): give the reader time instead.
    if (!url) return sleep(Math.min(4000, 800 + (text || '').length * 35));
    return new Promise((resolve) => {
      const done = () => { player.onended = player.onerror = player.onpause = null; resolve(); };
      player.onended = done;
      player.onerror = done;
      player.onpause = done;   // interrupted by the worker answering
      player.src = url;
      player.play().catch(done);
    });
  }

  function addLog(question, answer, value) {
    const empty = el.log.querySelector('.empty');
    if (empty) empty.remove();
    const li = document.createElement('li');
    const a = document.createElement('span'); a.className = 'a'; a.textContent = question;
    const arrow = document.createElement('span'); arrow.className = 'arrow'; arrow.textContent = '→';
    const w = document.createElement('span'); w.className = 'w'; w.textContent = answer;
    li.append(a, arrow, w);
    if (value !== undefined && value !== null) {
      const v = document.createElement('span'); v.className = 'val'; v.textContent = value;
      li.append(v);
    }
    el.log.append(li);
  }

  function showFact(parsed) {
    if (!parsed) return;
    const box = document.querySelector(`.fact[data-field="${parsed.field}"]`);
    if (!box) return;
    box.classList.add('filled');
    box.querySelector('b').textContent = parsed.field === 'days' ? `${parsed.value}` : inr(parsed.value);
  }

  function clearFacts() {
    document.querySelectorAll('.fact').forEach((b) => { b.classList.remove('filled'); b.querySelector('b').textContent = '—'; });
  }

  function factLabel(parsed) {
    if (!parsed) return null;
    return parsed.field === 'days' ? `${parsed.value} din` : inr(parsed.value);
  }

  function renderCase(c) {
    el.calc.replaceChildren();
    for (const line of c.breakdown) {
      const row = document.createElement('div');
      row.className = 'row' + (line.total ? ' total' : '');
      const left = document.createElement('div');
      left.textContent = line.label;
      if (line.math && line.math !== 'minus') {
        const s = document.createElement('small'); s.textContent = line.math; left.append(s);
      }
      const amt = document.createElement('div'); amt.className = 'amt'; amt.textContent = line.amount;
      row.append(left, amt);
      el.calc.append(row);
    }
    el.calc.classList.toggle('zero', c.outstanding <= 0);
    el.nodue.hidden = c.outstanding > 0;
    el.result.hidden = false;
  }

  function applyMode() {
    const typed = mode === 'text';
    el.chip.textContent = mode === 'text' ? 'Typed mode' : mode === 'scripted' ? 'Scripted demo' : 'Voice';
    el.mic.hidden = !sessionId || typed || mode === 'scripted' || finished;
    el.typed.hidden = !sessionId || !typed || finished;
    el.sw.hidden = !sessionId || mode === 'scripted' || finished || cfg.voiceOk === false;
    el.sw.textContent = typed ? 'Mic se boliye' : 'Likh kar jawab dijiye';
    if (typed && !el.typed.hidden) el.input.focus();
  }

  // ---------- server ----------
  async function sendTurn(fields) {
    const fd = new FormData();
    fd.append('mode', mode === 'scripted' ? 'scripted' : mode);
    if (sessionId) fd.append('session_id', sessionId);
    for (const [k, v] of Object.entries(fields || {})) {
      if (v instanceof Blob) fd.append(k, v, v.name || 'answer.webm'); else fd.append(k, v);
    }
    const resp = await fetch('/turn', { method: 'POST', body: fd });
    let data = {};
    try { data = await resp.json(); } catch { /* non-JSON error page */ }
    if (!resp.ok && !data.error) data.error = 'Server se jawab nahi aaya. Phir se koshish kijiye.';
    data.httpStatus = resp.status;
    return data;
  }

  async function handleReply(data, answerText) {
    if (data.error) {
      if (data.session_id) sessionId = data.session_id;
      setStatus(data.stt_failed ? 'Sun nahi paya, phir se boliye.' : data.error, true);
      if (data.key_missing) { mode = 'text'; applyMode(); }
      return false;
    }
    sessionId = data.session_id;
    if (answerText !== undefined) addLog(lastQuestion, answerText || '…', factLabel(data.parsed));
    showFact(data.parsed);
    if (data.state === 'ASK_DAYS' && answerText !== undefined && lastQuestion.startsWith('Confirm')) clearFacts();

    lastQuestion = data.agent_text;
    lastAudio = data.agent_audio_url;
    el.agent.textContent = data.agent_text;
    el.replay.hidden = !lastAudio;

    if (data.case) renderCase(data.case);
    if (data.fallback_text && mode === 'voice') { mode = 'text'; }

    finished = data.done;
    applyMode();
    setBusy(false, '');   // the worker may answer while the agent is still speaking (that stops the audio)
    await play(lastAudio, data.agent_text);

    // SHOW_PREVIEW → SEND_BUTTON: the message appears first, the button only after it.
    if (data.case && data.case.payment_request && !finished) {
      message = data.case.payment_request;
      el.preview.textContent = message;
      el.previewWrap.hidden = false;
      el.send.hidden = true;
      el.previewWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
      await sleep(1200);
      el.send.hidden = false;
      el.mic.hidden = true; el.typed.hidden = true; el.sw.hidden = true;
    }
    if (finished) { el.again.hidden = false; setStatus(''); }
    return true;
  }

  async function answer(fields, shownText) {
    setBusy(true, 'Samajh raha hoon…');
    try {
      const data = await sendTurn(fields);
      return await handleReply(data, data.error ? undefined : (data.heard ?? shownText));
    } catch {
      setStatus('Internet ya server se connection nahi hua. Phir se koshish kijiye.', true);
      return false;
    } finally {
      setBusy(false);
    }
  }

  // ---------- microphone ----------
  let recorder = null;
  let chunks = [];
  let stream = null;
  let stopTimer = null;

  function pickMime() {
    for (const m of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m;
    }
    return '';
  }

  async function startRecording() {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      setStatus('Is browser mein mic nahi chalta. Likh kar jawab dijiye.', true);
      mode = 'text'; applyMode(); return;
    }
    try {
      stream = stream || await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      setStatus('Mic ki permission nahi mili. Likh kar jawab dijiye.', true);
      mode = 'text'; applyMode(); return;
    }
    player.pause();
    const mime = pickMime();
    recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunks = [];
    recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    recorder.onstop = onRecorded;
    recorder.start();
    el.mic.classList.add('recording');
    el.mic.setAttribute('aria-label', 'Tap to stop');
    setStatus('Sun raha hoon… bolne ke baad phir dabaiye');
    stopTimer = setTimeout(stopRecording, MAX_RECORD_MS);
  }

  function stopRecording() {
    clearTimeout(stopTimer);
    if (recorder && recorder.state === 'recording') recorder.stop();
    el.mic.classList.remove('recording');
    el.mic.setAttribute('aria-label', 'Tap to speak');
  }

  async function onRecorded() {
    const type = recorder.mimeType || 'audio/webm';
    const blob = new Blob(chunks, { type });
    if (blob.size < 1500) { setStatus('Sun nahi paya, phir se boliye.', true); return; }
    const ext = type.includes('mp4') ? 'mp4' : type.includes('ogg') ? 'ogg' : 'webm';
    const file = new File([blob], `answer.${ext}`, { type });
    await answer({ audio: file });
  }

  // ---------- scripted demo (no mic, no external network) ----------
  async function runScript() {
    el.mic.hidden = true;
    for (let i = 0; i < SCRIPT.length && !finished; i++) {
      await sleep(500);
      setStatus('Mazdoor bol raha hai…');
      await play(`/static/demo/worker_${i}.mp3`, SCRIPT[i]);
      const ok = await answer({ text: SCRIPT[i] }, SCRIPT[i]);
      if (!ok) return;
      if (!el.send.hidden) break;   // preview + Send button are up: the presenter taps Send
    }
  }

  // ---------- wiring ----------
  el.start.addEventListener('click', async () => {
    el.start.hidden = true;
    // Unlock audio playback on this tap (autoplay rules), then let the agent speak first.
    player.src = 'data:audio/wav;base64,UklGRrQBAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YZABAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA';
    player.play().catch(() => {});
    setBusy(true, 'Shuru ho raha hai…');
    try {
      const data = await sendTurn();
      setBusy(false);
      await handleReply(data);
      if (mode === 'scripted') runScript();
    } catch {
      setBusy(false);
      el.start.hidden = false;
      setStatus('Server se connection nahi hua.', true);
    }
  });

  el.mic.addEventListener('click', () => {
    if (busy || finished) return;
    if (recorder && recorder.state === 'recording') stopRecording(); else startRecording();
  });

  el.typed.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = el.input.value.trim();
    if (!text || busy) return;
    player.pause();
    el.input.value = '';
    await answer({ text }, text);
    if (!el.typed.hidden) el.input.focus();
  });

  el.sw.addEventListener('click', () => {
    if (recorder && recorder.state === 'recording') stopRecording();
    mode = mode === 'text' ? 'voice' : 'text';
    applyMode();
  });

  el.replay.addEventListener('click', () => play(lastAudio, lastQuestion));

  el.send.addEventListener('click', async () => {
    // Plain deep link: no WhatsApp API. The worker picks the contractor's chat and presses send.
    window.open('https://wa.me/?text=' + encodeURIComponent(message), '_blank', 'noopener');
    try {
      const data = await sendTurn({ event: 'sent' });
      if (!data.error) {
        finished = true;
        lastQuestion = data.agent_text; lastAudio = data.agent_audio_url;
        el.agent.textContent = data.agent_text;
        el.again.hidden = false;
        play(lastAudio, data.agent_text);
      }
    } catch { /* WhatsApp already opened; nothing else to do */ }
  });

  el.again.addEventListener('click', () => location.reload());

  applyMode();
  el.chip.textContent = mode === 'text' ? 'Typed mode' : mode === 'scripted' ? 'Scripted demo' : 'Voice';
})();
