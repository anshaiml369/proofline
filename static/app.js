// PagarSaathi front end.
// Voice IN is Wispr Flow: the worker dictates into the text box (double-tap Fn on Mac, the
// Wispr Flow keyboard on iPhone). This page has no microphone code by design: the round "Bolo"
// button only focuses the box, so Wispr Flow's words land there, and shows what the input is doing.
// Voice OUT is Sarvam Bulbul (natural Hindi) when the server has a key, or a pre-recorded clip;
// otherwise the browser's own SpeechSynthesis (free). No arithmetic happens here: every number on the
// card comes from the server (wage_math.py). The count-up only animates the server's final value.
(() => {
  const params = new URLSearchParams(location.search);
  const scripted = params.get('mode') === 'scripted';
  const textMode = params.get('mode') === 'text';
  const debug = params.get('debug') === '1';
  const dlog = (...a) => { if (debug) console.log('[PagarSaathi]', new Date().toISOString().slice(11, 23), ...a); };

  // The demo conversation: what the worker says (via Wispr Flow) at each turn.
  // Keep in sync with scripts/make_demo_audio.py. A context line and a three-fact bundle, ending at ₹700.
  const SCRIPT = [
    'Thekedar ne poore paise nahi diye. Teen saal se unke saath hoon, pichhle hafte bimar bhi tha.',
    'Chhe din kaam kiya, saat sau roz, paanch sau advance mila tha.',
    'Teen hazaar mile.',
    'Haan.',
    'Haan.',
  ];

  // UI strings per language. Agent lines come from the server; these are the page's own labels.
  const UI = {
    hi: { tagline: 'Mazdoori ka hisaab, aawaz se', start: 'Shuru karein', bolo: 'Dabaiye, phir Wispr Flow se boliye',
      continue: 'Continue', hisaab: 'Hisaab', baaki: 'Baaki', confirmed: 'Confirmed',
      nodue: 'Hisaab ke hisaab se koi paisa baaki nahi hai.', case_id: 'Case ID',
      hash_caption: 'Yeh hash case ka fingerprint hai. Case mein koi badlav hua to hash mel nahi khayega, isse badlav pakda ja sakta hai.',
      escalate: 'Escalate: shikayat ka draft', share: 'Union / legal aid', delete: 'Case delete', draft: 'Shikayat ka draft (copy karke SAMADHAN par dijiye)',
      copy: 'Copy karein', copied: 'Copy ho gaya', msg: 'Thekedar ko message', send: 'WhatsApp par bhejein', again: 'Naya hisaab', log: 'Baatcheet',
      notes: 'Aapne bataya', f_days: 'Din', f_rate: 'Roz', f_advance: 'Advance', f_payments: 'Mila', sent: 'Bheja gaya',
      reminder: 'Thekedar ka vaada', followup: 'Pichhla case', beta: '' },
    mr: { tagline: 'मजुरीचा हिशोब, आवाजाने', start: 'सुरू करा', bolo: 'दाबा, मग Wispr Flow ने बोला',
      continue: 'पुढे', hisaab: 'हिशोब', baaki: 'बाकी', confirmed: 'निश्चित',
      nodue: 'हिशोबानुसार कोणतेही पैसे बाकी नाहीत.', case_id: 'केस आयडी',
      hash_caption: 'हा हॅश केसचा फिंगरप्रिंट आहे. केसमध्ये बदल झाला तर हॅश जुळणार नाही, त्यामुळे बदल पकडता येतो.',
      escalate: 'तक्रार: मसुदा', share: 'युनियन / कायदेशीर मदत', delete: 'केस डिलीट', draft: 'तक्रारीचा मसुदा (कॉपी करून समाधानवर द्या)',
      copy: 'कॉपी करा', copied: 'कॉपी झाले', msg: 'ठेकेदाराला मेसेज', send: 'व्हॉट्सॲपवर पाठवा', again: 'नवीन हिशोब', log: 'संवाद',
      notes: 'तुम्ही सांगितले', f_days: 'दिवस', f_rate: 'रोज', f_advance: 'ॲडव्हान्स', f_payments: 'मिळाले', sent: 'पाठवले',
      reminder: 'ठेकेदाराचे वचन', followup: 'मागची केस', beta: '' },
    en: { tagline: 'Your wages, worked out by voice', start: 'Start', bolo: 'Tap, then speak with Wispr Flow',
      continue: 'Continue', hisaab: 'Calculation', baaki: 'Owed', confirmed: 'Confirmed',
      nodue: 'By this calculation nothing is owed.', case_id: 'Case ID',
      hash_caption: "This hash is the case's fingerprint. If the case is changed, the hash will no longer match, so the change can be detected.",
      escalate: 'Escalate: complaint draft', share: 'Union / legal aid', delete: 'Delete case', draft: 'Complaint draft (copy it to SAMADHAN)',
      copy: 'Copy', copied: 'Copied', msg: 'Message to contractor', send: 'Send on WhatsApp', again: 'New calculation', log: 'Conversation',
      notes: 'You told us', f_days: 'Days', f_rate: 'Daily', f_advance: 'Advance', f_payments: 'Paid', sent: 'Sent',
      reminder: "Contractor's promise", followup: 'Earlier case',
      beta: 'Beta: the agent replies in your language, but the read-back and the result are in Hindi.' },
    bn: { tagline: 'মজুরির হিসাব, কণ্ঠে', start: 'শুরু করুন', continue: 'এগিয়ে যান', hisaab: 'হিসাব', baaki: 'বাকি',
      f_days: 'দিন', f_rate: 'রোজ', f_advance: 'অগ্রিম', f_payments: 'পেয়েছি', again: 'নতুন হিসাব', log: 'কথোপকথন',
      beta: 'বেটা: এজেন্ট বাংলায় উত্তর দেয়, কিন্তু পড়ে শোনানো হিসাব ও ফল হিন্দিতে।' },
    ta: { tagline: 'கூலி கணக்கு, குரலில்', start: 'தொடங்கு', continue: 'தொடர்', hisaab: 'கணக்கு', baaki: 'பாக்கி',
      f_days: 'நாள்', f_rate: 'தினக்கூலி', f_advance: 'முன்பணம்', f_payments: 'பெற்றது', again: 'புதிய கணக்கு', log: 'உரையாடல்',
      beta: 'பீட்டா: முகவர் தமிழில் பதில் தருவார், ஆனால் சரிபார்ப்பும் முடிவும் இந்தியில்.' },
    te: { tagline: 'కూలీ లెక్క, గొంతుతో', start: 'ప్రారంభించండి', continue: 'కొనసాగించు', hisaab: 'లెక్క', baaki: 'బాకీ',
      f_days: 'రోజులు', f_rate: 'రోజు కూలీ', f_advance: 'అడ్వాన్స్', f_payments: 'అందింది', again: 'కొత్త లెక్క', log: 'సంభాషణ',
      beta: 'బీటా: ఏజెంట్ తెలుగులో జవాబిస్తారు, కానీ చదివి వినిపించే లెక్క, ఫలితం హిందీలో.' },
    bho: { tagline: 'मजूरी के हिसाब, आवाज से', start: 'सुरू करीं', again: 'नया हिसाब',
      beta: 'Beta: Bhojpuri mein jawab, lekin read-back aur nateeja Hindi mein, Hindi aawaz se.' },
  };
  UI['en-mix'] = UI.en;
  const BETA = new Set(['bho', 'bn', 'ta', 'te', 'en-mix']);
  const VOICE_BCP = { hi: 'hi-IN', mr: 'mr-IN', bn: 'bn-IN', ta: 'ta-IN', te: 'te-IN' };
  const ERR_HEARD = 'Sun nahi paya, phir se boliye.';
  let lang = 'hi';
  try { lang = localStorage.getItem('ps_lang') || 'hi'; } catch { /* storage blocked */ }
  let langChosen = false;       // the worker picked it on the toggle (sent to the server)
  const t = (key) => (UI[lang] && UI[lang][key]) || UI.hi[key] || (UI.en[key] || '');

  const $ = (id) => document.getElementById(id);
  const el = {
    q: $('q'), agent: $('agent-text'), speaking: $('speaking'), replay: $('replay'), bolo: $('bolo'), caption: $('bolo-caption'),
    form: $('answer-form'), answer: $('answer'), cont: $('continue'), status: $('status'), error: $('error'), assist: $('assist'),
    result: $('result'), calc: $('calc'), nodue: $('nodue'), previewWrap: $('preview-wrap'),
    preview: $('preview'), send: $('send'), again: $('again'), log: $('log'), chip: $('mode-chip'),
    keyless: $('keyless'), blocked: $('popup-blocked'), toast: $('toast'),
  };
  const show = (node, on = true) => node.classList.toggle('hidden', !on);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const inr = (n) => '₹' + Number(n).toLocaleString('en-IN');

  function applyLang() {
    document.documentElement.lang = lang === 'en-mix' ? 'en' : lang;
    document.querySelectorAll('[data-i18n]').forEach((n) => { const v = t(n.dataset.i18n); if (v) n.textContent = v; });
    const note = $('beta-note');
    note.textContent = BETA.has(lang) ? (UI[lang].beta || UI.en.beta) : '';
    show(note, BETA.has(lang));
    $('lang').value = lang;
    el.caption.textContent = started ? t('bolo') : t('start');
  }

  // ---------- motion (motion.dev, vanilla). One guard for reduced motion: opacity only. ----------
  const reduced = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  const M = window.Motion && window.Motion.animate ? window.Motion : null;
  const SPRING = M ? { type: M.spring, stiffness: 300, damping: 30 } : {};
  function anim(node, keyframes, options = {}) {
    if (!node) return Promise.resolve();
    let kf = keyframes;
    let opts = options;
    if (reduced.matches) {
      if (!kf.opacity) return Promise.resolve();          // nothing moves or scales
      kf = { opacity: kf.opacity };
      opts = { duration: 0.2, ease: 'linear' };
    }
    if (!M) { node.style.opacity = ''; return Promise.resolve(); }   // CDN failed: no animation, page still works
    try {
      const c = M.animate(node, kf, opts);
      return c && c.finished ? c.finished : Promise.resolve(c);
    } catch (e) { dlog('animate failed', e); node.style.opacity = ''; return Promise.resolve(); }
  }
  // ₹0 → final value, once per case; with reduced motion the final value appears at once.
  function countUp(node, value) {
    const final = inr(value);
    if (reduced.matches || value <= 0) { node.textContent = final; return; }
    const start = performance.now();
    const step = (now) => {
      const p = Math.max(0, Math.min(1, (now - start) / 600));
      const eased = 1 - Math.pow(1 - p, 3);                     // ease-out
      node.textContent = p < 1 ? inr(Math.round(value * eased)) : final;
      if (p < 1) requestAnimationFrame(step);
    };
    node.textContent = inr(0);
    requestAnimationFrame(step);
  }

  // ---------- the Bolo button's states ----------
  let started = false;
  let listenTimer = null;
  function setBolo(state) {
    el.bolo.dataset.state = state;
    el.bolo.setAttribute('aria-disabled', state === 'disabled' ? 'true' : 'false');
  }
  function listening() {            // Wispr Flow text is arriving in the box
    if (el.bolo.dataset.state === 'processing' || el.bolo.dataset.state === 'disabled') return;
    setBolo('listening');
    clearTimeout(listenTimer);
    listenTimer = setTimeout(() => { if (el.bolo.dataset.state === 'listening') setBolo('idle'); }, 1000);
  }

  // ---------- the question: fade out, swap, fade in ----------
  let qSeq = 0;
  async function setQuestion(text) {
    const seq = ++qSeq;
    if (el.agent.textContent === text) return;
    await anim(el.agent, { opacity: [1, 0] }, { duration: 0.15, ease: 'easeIn' });
    if (seq !== qSeq) return;
    el.agent.textContent = text;
    el.agent.classList.toggle('long', text.length > 90 && text.length <= 160);
    el.agent.classList.toggle('xlong', text.length > 160);
    await anim(el.agent, { opacity: [0, 1], y: [8, 0] }, { duration: 0.2, ease: 'easeOut' });
  }
  // keep the sticky question's height in a CSS variable, so scrolled-to blocks land below it
  if (window.ResizeObserver) {
    new ResizeObserver(() => document.documentElement.style.setProperty('--qh', el.q.offsetHeight + 'px')).observe(el.q);
  }
  window.addEventListener('scroll', () => el.q.classList.toggle('stuck', window.scrollY > el.q.offsetTop + 4), { passive: true });

  let sessionId = null;
  let last = null;            // last server reply (for replay)
  let busy = false;
  let message = '';
  let scriptStopped = false;
  let countedFor = null;
  const player = new Audio();
  const played = new Set();      // "state|url": a clip never plays twice in the same state
  // Debug: every media event, so a stray or repeated clip shows up in the console (?debug=1).
  for (const ev of ['play', 'pause', 'ended', 'error']) {
    player.addEventListener(ev, () => dlog('audio', ev, player.currentSrc.split('/').pop(),
      ev === 'error' && player.error ? 'code ' + player.error.code : ''));
  }
  // A 0.1 s silent WAV, played inside the first tap so later clips are allowed to play (Safari/iOS).
  const SILENT = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';

  // ---------- voice out ----------
  let voices = [];
  const loadVoices = () => { voices = window.speechSynthesis ? speechSynthesis.getVoices() : []; };
  loadVoices();
  if (window.speechSynthesis) speechSynthesis.onvoiceschanged = loadVoices;
  const voiceFor = (code) => voices.find((v) => v.lang.replace('_', '-').toLowerCase().startsWith(code.toLowerCase()));
  const hindiVoice = () => voiceFor('hi');

  function stopSpeaking() {
    if (window.speechSynthesis) speechSynthesis.cancel();
    player.pause();
  }

  function utter(text, voice, bcp) {
    return new Promise((resolve) => {
      dlog('browser voice', bcp, voice ? voice.name : '(default)', JSON.stringify(text));
      const u = new SpeechSynthesisUtterance(text);
      if (voice) u.voice = voice;
      u.lang = bcp;
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
      let begun = false;
      const finish = (ok) => { player.onended = player.onerror = player.onpause = player.onplaying = null; resolve(ok); };
      player.onplaying = () => { begun = true; };
      player.onended = () => finish(true);
      player.onpause = () => finish(begun);
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
    const clean = (s) => s.replace(/\s*[?？]+/g, '।').replace(/।\s*।/g, '।');
    try {
      if (reply.agent_audio_url && await playClip(reply.agent_audio_url)) return reply.audio_source || 'recorded';
      const bcp = VOICE_BCP[reply.voice_lang] || 'hi-IN';
      // the line's own language voice; Marathi (Devanagari) can fall back to a Hindi voice
      const own = window.speechSynthesis && (voiceFor(bcp.slice(0, 2)) || (['hi-IN', 'mr-IN'].includes(bcp) && hindiVoice()));
      if (own) { await utter(clean(reply.speak_text), own, own.lang || bcp); return 'browser'; }
      if (window.speechSynthesis && voices.length) { await utter(clean(reply.agent_text), null, 'en-IN'); return 'browser'; }
      await sleep(Math.min(3500, 600 + reply.agent_text.length * 30));       // no voice at all: reading time
      return 'none';
    } finally {
      show(el.speaking, false);
    }
  }

  // ---------- status and errors ----------
  function setStatus(text) { el.status.textContent = text || ''; }
  function clearError() { el.error.textContent = ''; show(el.error, false); }
  // Always Hinglish, never JSON: the server's own message, or "Sun nahi paya…".
  function showError(text, { inLog = false } = {}) {
    const line = text && text !== ERR_HEARD ? ERR_HEARD + ' ' + text : ERR_HEARD;
    setStatus('');
    el.error.textContent = line;
    show(el.error, true);
    anim(el.error, { opacity: [0, 1] }, { duration: 0.2 });
    anim(el.bolo, { x: [0, -6, 6, -3, 0] }, { duration: 0.3, ease: 'easeOut' });
    if (el.bolo.dataset.state !== 'disabled') setBolo('idle');
    if (inLog) bubble(line, 'agent');
  }

  const TEXT_LABEL = { llm: 'Text: LLM', rules: 'Text: Rules' };
  const VOICE_LABEL = { recorded: 'Voice: Recorded', sarvam: 'Voice: Sarvam', browser: 'Voice: Browser', none: 'Voice: off' };
  const INPUT_LABEL = { typed: 'Wispr Flow / typed', scripted: 'Scripted demo' };

  // Small grey provenance line under a bubble: where this line came from.
  function badge(li, text) {
    const b = document.createElement('li');
    b.setAttribute('role', 'note');
    b.className = 'prov ' + (li.classList.contains('worker') ? 'right' : 'left');
    b.textContent = text;
    li.after(b);
    el.log.scrollTop = el.log.scrollHeight;
    return b;
  }

  function bubble(text, who, tag) {
    const empty = el.log.querySelector('.empty');
    if (empty) empty.remove();
    const li = document.createElement('li');
    li.className = 'msg ' + (who === 'agent' ? 'agent' : 'worker');
    li.textContent = text;
    if (tag) {
      const s = document.createElement('span');
      s.className = 'tag';
      s.textContent = tag;
      li.append(s);
    }
    el.log.append(li);
    el.log.scrollTop = el.log.scrollHeight;            // the latest line stays in view
    anim(li, { opacity: [0, 1], y: [6, 0] }, { duration: 0.2, ease: 'easeOut' });
    return li;
  }

  function showFact(parsed) {
    const box = parsed && document.querySelector(`.fact[data-field="${parsed.field}"]`);
    if (!box) return;
    box.classList.add('on');
    box.querySelector('b').textContent = (parsed.field === 'days' ? parsed.value : inr(parsed.value)) + (parsed.assumed ? '?' : '');
  }

  function showFacts(facts) {      // the LLM can hear several facts in one sentence
    if (!facts) return;
    clearFacts();
    for (const [field, value] of Object.entries(facts)) showFact({ field, value });
  }

  function showNotes(notes) {     // context the agent kept: hospital, loan, years...
    const list = $('notes');
    list.replaceChildren();
    for (const n of notes || []) {
      const li = document.createElement('li');
      li.textContent = n;
      list.append(li);
    }
    show($('notes-wrap'), !!(notes && notes.length));
  }

  function clearFacts() {
    document.querySelectorAll('.fact').forEach((box) => {
      box.classList.remove('on');
      box.querySelector('b').textContent = '—';
    });
  }

  function factTag(parsed) {
    if (!parsed) return null;
    return (parsed.field === 'days' ? `${parsed.value} din` : inr(parsed.value)) + (parsed.assumed ? ' (maana)' : '');
  }

  // Inline icons for the calculation lines (constant markup, no user text).
  const SVG = (body, color = '#1a1a1a', w = 2) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
  const ICONS = {
    calendar: SVG('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>'),
    clock: SVG('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    minus: SVG('<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>'),
    rupee: SVG('<path d="M6 3h12M6 8h12M9 3c4 0 6 2 6 5s-2 5-6 5H6l8 8"/>'),
    wallet: SVG('<path d="M3 7h15a3 3 0 0 1 3 3v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/><path d="M3 7l12-4v4"/><circle cx="16.5" cy="14" r="1.2"/>'),
    check: SVG('<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>', '#034f46', 2.4),
  };
  const DOT = SVG('<circle cx="12" cy="12" r="3"/>');

  function renderCase(c) {
    el.calc.replaceChildren();
    const out = $('outstanding');
    out.classList.toggle('zero', c.outstanding <= 0);
    for (const line of c.breakdown) {
      const row = document.createElement('div');
      row.className = 'row' + (line.total ? ' total' : '');
      row.insertAdjacentHTML('afterbegin', ICONS[line.icon] || DOT);
      const dt = document.createElement('dt');
      dt.textContent = line.label;
      if (line.math && line.math !== 'minus') {
        const s = document.createElement('small');
        s.textContent = line.math;
        dt.append(s);
      }
      const dd = document.createElement('dd');
      dd.textContent = line.amount;
      row.append(dt, dd);
      el.calc.append(row);
    }
    show(el.nodue, c.outstanding <= 0);
    const key = sessionId + '|' + c.outstanding + '|' + c.breakdown.map((l) => l.amount).join(',');
    const entering = el.result.classList.contains('hidden');
    show(el.result, true);
    if (entering) anim(el.result, { opacity: [0, 1], y: [24, 0], scale: [0.96, 1] }, SPRING);
    if (key !== countedFor) { countedFor = key; countUp(out, Math.max(0, c.outstanding)); }
    else out.textContent = inr(Math.max(0, c.outstanding));
  }

  const when = (iso) => new Date(iso).toLocaleString(lang === 'mr' ? 'mr-IN' : 'en-IN',
    { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });

  function renderAudit(d) {
    if (!d.case_hash_short) return;
    show($('audit'), true);
    $('hash').textContent = d.case_hash_short;
    $('hash').title = d.case_hash;
    $('share').href = '/case/' + d.session_id + '/share';
    if (d.sent_at) {
      const line = t('sent') + ': ' + when(d.sent_at);
      $('sent-at').textContent = '✓ ' + line;
      show($('sent-at'), true);
      showToast(line);
    }
    if (d.commitment_date) { $('reminder').textContent = '⏰ ' + t('reminder') + ': ' + d.commitment_date; show($('reminder'), true); }
    if (d.escalation_draft) showDraft(d.escalation_draft);
  }

  function showToast(text) {
    $('toast-text').textContent = text;
    if (!el.toast.classList.contains('hidden')) return;
    show(el.toast, true);
    document.body.classList.add('has-toast');
    anim(el.toast, { opacity: [0, 1], y: [24, 0] }, SPRING);
  }

  function showDraft(text) {
    $('draft').textContent = text;
    const wrap = $('draft-wrap');
    if (wrap.classList.contains('hidden')) { show(wrap, true); anim(wrap, { opacity: [0, 1], y: [8, 0] }, { duration: 0.2 }); }
  }

  function renderDebug(d) {
    if (!debug) return;
    show($('debug'), true);
    $('debug').textContent = 'node_path: ' + (d.node_path || []).join(' → ') + '\npolicy: ' + d.policy_source +
      ' · action: ' + (d.action || '-') + ' · lang: ' + d.language + ' · voice: ' + d.voice_lang +
      (d.llm_error ? ' · llm_error: ' + d.llm_error : '') + (d.case_hash ? '\nsha256: ' + d.case_hash : '');
  }

  // ---------- server ----------
  async function postJSON(url, body) {
    const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    let data = {};
    try { data = await resp.json(); } catch { /* an HTML or empty error page: never shown */ }
    if (!data || typeof data !== 'object') data = {};
    if (!resp.ok && typeof data.error !== 'string') data.error = 'Server se jawab nahi aaya. Thodi der mein phir koshish kijiye.';
    return data;
  }
  const post = (body) => postJSON('/turn', { ...body, session_id: sessionId, mode: scripted ? 'scripted' : '',
    ...(langChosen ? { language: lang } : {}) });

  async function handle(data, saidText) {
    if (data.error) { showError(data.error, { inLog: true }); return false; }
    clearError();
    sessionId = data.session_id;
    if (saidText !== undefined) badge(bubble(saidText, 'worker', factTag(data.parsed)), INPUT_LABEL[data.input_source] || 'Typed');
    if (data.state === 'ASK_DAYS' && saidText !== undefined && last && last.state === 'CONFIRM') clearFacts();
    if (data.facts) showFacts(data.facts); else showFact(data.parsed);
    if (data.parsed && data.parsed.assumed) showFact(data.parsed);
    showNotes(data.context_notes);
    if (data.language && data.language !== lang && !langChosen) { lang = data.language; applyLang(); }
    if (data.prior_case) {
      const chip = $('followup-chip');
      chip.textContent = t('followup') + ': ' + inr(data.prior_case.outstanding) + ' · ' + (data.prior_case.case_hash_short || '') +
        (data.prior_case.commitment_date ? ' · ⏰ ' + data.prior_case.commitment_date : '');
      show(chip, true);
    }
    if (data.deleted) {
      show($('audit'), false); show($('draft-wrap'), false); show(el.result, false); show($('followup-chip'), false);
      try { localStorage.removeItem('ps_last_case'); } catch { /* storage blocked */ }
    }

    last = data;
    setQuestion(data.agent_text);
    const prov = badge(bubble(data.agent_text, 'agent'), TEXT_LABEL[data.text_source] || 'Text: Rules');
    dlog('reply', data.state, data.text_source, data.audio_source, JSON.stringify(data.agent_text));
    show(el.replay, true);
    show(el.assist, !!data.needs_assistance && !data.case_data);
    setStatus('');
    if (data.case_data) renderCase(data.case_data);
    renderAudit(data);
    renderDebug(data);
    if (data.case_hash_short) {
      try { localStorage.setItem('ps_last_case', JSON.stringify({ session_id: data.session_id, at: Date.now() })); } catch { /* storage blocked */ }
    }

    const finished = data.done;
    const preview = data.state === 'SHOW_PREVIEW' && data.case_data && data.case_data.payment_request;
    if (finished || preview) { show(el.form, false); setBolo('disabled'); } else setBolo('idle');
    if (finished) show(el.again, true);
    if (!finished && !preview && !scripted) el.answer.focus({ preventScroll: true });   // Wispr Flow types into the focused field

    const spoken = speak(data).then((voice) => { prov.textContent += ' · ' + VOICE_LABEL[voice]; });
    if (preview) {
      // SHOW_PREVIEW: the message springs in first, the Send button after it.
      message = data.case_data.payment_request;
      el.preview.textContent = message;
      if (el.previewWrap.classList.contains('hidden')) {
        show(el.previewWrap, true);
        anim(el.previewWrap, { opacity: [0, 1], y: [24, 0], scale: [0.96, 1] }, SPRING);
      }
      el.previewWrap.scrollIntoView({ behavior: reduced.matches ? 'auto' : 'smooth', block: 'start' });
      await sleep(1200);
      if (el.send.classList.contains('hidden') && !last.sent_at) {
        show(el.send, true);
        anim(el.send, { opacity: [0, 1], y: [8, 0] }, { duration: 0.2, ease: 'easeOut' });
      }
    }
    await spoken;
    return true;
  }

  let queued = false;
  async function submit(text) {
    if (scriptStopped && scripted) return;
    if (!text) { showError('Pehle Wispr Flow se boliye ya likhiye, phir Continue dabaiye.'); el.answer.focus(); return; }
    if (busy) { queued = true; setStatus('Ek second…'); return; }   // sent when the current reply arrives
    busy = true;
    el.cont.disabled = true;
    setBolo('processing');
    stopSpeaking();
    clearError();
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
      showError('Server se connection nahi hua.', { inLog: true });
    } finally {
      busy = false;
      el.cont.disabled = false;
      if (el.bolo.dataset.state === 'processing') setBolo('idle');
    }
  }

  // ---------- scripted demo: fills the box as Wispr Flow would, presses Continue ----------
  async function runScript() {
    for (const line of SCRIPT) {
      await sleep(900);
      el.answer.focus({ preventScroll: true });
      for (let i = 1; i <= line.length; i++) {           // text "appears" like dictation
        el.answer.value = line.slice(0, i);
        listening();
        await sleep(18);
      }
      await sleep(1100);
      await anim(el.cont, { scale: [1, 0.97, 1] }, { duration: 0.12 });
      await submit(el.answer.value.trim());
      if (last && (last.state === 'SHOW_PREVIEW' || last.done)) break;   // stop cleanly: never type past the end
    }
    scriptStopped = true;
    dlog('script finished at', last && last.state);
  }

  // ---------- wiring ----------
  async function start() {
    started = true;
    applyLang();
    // Unlock the audio element inside this tap, so later clips may play without one.
    player.src = SILENT;
    player.play().then(() => { if (player.src === SILENT) player.pause(); }).catch(() => {});
    // Unlock speech on this tap (browsers need a user gesture before talking).
    if (window.speechSynthesis) speechSynthesis.speak(new SpeechSynthesisUtterance(''));
    show(el.form, true);
    anim(el.form, { opacity: [0, 1], y: [8, 0] }, { duration: 0.2, ease: 'easeOut' });
    show($('wispr-hint'), false);   // the answer box carries the Wispr Flow label from here on
    setBolo('processing');
    setStatus('Shuru ho raha hai…');
    try {
      let prior = null;
      try { prior = scripted ? null : JSON.parse(localStorage.getItem('ps_last_case') || 'null'); } catch { /* storage blocked */ }
      const ok = await handle(await post(prior ? { prior_session: prior.session_id } : {}));
      if (ok && scripted) runScript();
      if (!ok) { started = false; applyLang(); }
    } catch {
      started = false;
      applyLang();
      showError('Server se connection nahi hua.');
    }
  }

  el.bolo.addEventListener('click', () => {
    anim(el.bolo, { scale: [1, 0.97, 1] }, { duration: 0.12 });
    if (!started) { start(); return; }
    if (el.bolo.dataset.state === 'disabled') return;
    el.answer.focus({ preventScroll: true });
    el.form.scrollIntoView({ behavior: reduced.matches ? 'auto' : 'smooth', block: 'nearest' });
  });

  el.form.addEventListener('submit', (e) => { e.preventDefault(); submit(el.answer.value.trim()); });
  el.answer.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(el.answer.value.trim()); }
  });
  el.answer.addEventListener('input', () => { if (el.answer.value) { stopSpeaking(); listening(); } });
  el.replay.addEventListener('click', () => last && speak(last, { force: true }));

  async function markSent() {
    try {
      const data = await postJSON('/mark-sent', { session_id: sessionId, mode: scripted ? 'scripted' : '' });
      if (data.error) { showError(data.error); return; }
      last = data;
      renderAudit(data);
      renderDebug(data);
      show(el.send, false);
      show(el.blocked, false);
      setQuestion(data.agent_text);
      const prov = badge(bubble(data.agent_text, 'agent'), TEXT_LABEL[data.text_source] || 'Text: Rules');
      show(el.again, true);
      speak(data).then((voice) => { prov.textContent += ' · ' + VOICE_LABEL[voice]; });
    } catch { /* WhatsApp already opened; the card stays as it was */ }
  }

  el.send.addEventListener('click', async () => {
    // Plain deep link, no WhatsApp API: the worker picks the contractor's chat and presses send.
    // Opened first, inside the tap, so the browser allows the new tab.
    const w = window.open('https://wa.me/?text=' + encodeURIComponent(message), '_blank');
    await anim(el.send, { scale: [1, 0.97, 1] }, { duration: 0.12 });
    if (!w) { show(el.blocked, true); anim(el.blocked, { opacity: [0, 1] }, { duration: 0.2 }); return; }
    try { w.opener = null; } catch { /* cross-origin already */ }
    anim(el.previewWrap, { opacity: [1, 0.6] }, { duration: 0.2 });
    markSent();
  });

  $('copy-msg').addEventListener('click', () => {
    const b = $('copy-msg');
    (navigator.clipboard ? navigator.clipboard.writeText(message) : Promise.reject())
      .then(() => { b.textContent = t('copied'); markSent(); }, () => {});
  });

  el.again.addEventListener('click', () => location.reload());

  $('escalate').addEventListener('click', async () => {
    const errLine = $('escalate-error');
    show(errLine, false);
    try {
      const d = await postJSON('/escalate', { session_id: sessionId });
      if (d.escalation_draft) {
        showDraft(d.escalation_draft);
        $('draft-wrap').scrollIntoView({ behavior: reduced.matches ? 'auto' : 'smooth', block: 'start' });
        return;
      }
      errLine.textContent = 'Draft nahi bana. ' + (d.error || 'Phir se dabaiye.');
    } catch {
      errLine.textContent = 'Draft nahi bana. Server se connection nahi hua.';
    }
    show(errLine, true);
  });
  $('copy-draft').addEventListener('click', () => {
    const b = $('copy-draft');
    (navigator.clipboard ? navigator.clipboard.writeText($('draft').textContent) : Promise.reject())
      .then(() => { b.textContent = t('copied'); }, () => {});
  });
  // Delete goes through the agent: it asks "Pakka?" and deletes only after a spoken (dictated) yes.
  $('delete').addEventListener('click', () => { show(el.form, true); setBolo('idle'); submit('mera case delete karo'); });

  $('lang').addEventListener('change', (e) => {
    lang = e.target.value;
    langChosen = true;
    try { localStorage.setItem('ps_lang', lang); } catch { /* storage blocked */ }
    applyLang();
  });
  try { langChosen = !!localStorage.getItem('ps_lang'); } catch { /* storage blocked */ }
  applyLang();
  if (scripted) show(el.chip, true);
  if (textMode) { el.chip.textContent = 'Text mode'; show(el.chip, true); }

  // Tell a judge up front when the server runs without keys (rules + recorded voice).
  fetch('/health').then((r) => r.json()).then((h) => {
    dlog('health', JSON.stringify(h));
    if (h.mode === 'keyless' && !scripted) {
      el.keyless.textContent = 'Demo mode: rules + recorded voice (API keys nahi hain)';
      el.keyless.title = 'LLM aur Sarvam voice ke liye server par ' + h.missing.join(' aur ') + ' set kijiye.';
      show(el.keyless, true);
    }
  }).catch(() => {});

  // The page's first entrance: one spring, the same guard as everything else.
  anim(document.querySelector('main'), { opacity: [0, 1], y: [24, 0] }, SPRING);
})();
