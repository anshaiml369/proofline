# What PagarSaathi does not claim

PagarSaathi works out a number and helps the worker act on it. This page lists what it cannot do, so nobody relies on it for more.

## It does not enforce anything

- **We do not guarantee payment.** The WhatsApp message is a request. The contractor can ignore it.
- **The complaint draft is only a draft.** Nothing is filed for the worker. There is no SAMADHAN or labour-office API behind the Escalate button; the worker or a volunteer copies the text and files it.
- **It is not legal advice.** The figure is arithmetic on what the worker said. Whether the agreed rate was legal (for example, below the minimum wage) is not checked.

## The hash shows changes; it does not prevent them

- The sha256 hash makes any later edit to the stored case detectable: recompute it and it no longer matches. It does not stop anyone from editing the database, and it does not prove the worker's numbers are true.
- The hash is not anchored anywhere outside our server (no timestamping service, no blockchain). Someone who controls the server could change a case and its hash together. Its value comes from the worker keeping the short hash (on the card, in the WhatsApp message they sent, in the complaint draft) and checking it later.

## The numbers are only as good as the conversation

- **Everything comes from the worker's memory.** There is no attendance record, no contractor data and no document check.
- **The read-back is the safety net.** The LLM can mishear; Python only accepts numbers the worker said, and the worker confirms all of them before any maths. A worker who says "haan" to a wrong read-back gets a wrong figure.
- **Simple cases only:** one daily rate, plus optional overtime and deductions. Half days, several rates in one week, piece rates and bonuses are not modelled.
- **Contradictions are caught only on the LLM path,** when a number changes without a word like "nahi" or "galat". The rules path takes the first value it heard.

## Measured, but small

- The before/after numbers in [EVALUATION.md](EVALUATION.md) come from **32 scripted cases written by us**. That is a small set, and the scripted worker does not adapt. The first held-out v3 run was 97.7% slot accuracy and 90.6% maths correctness; later runs, after one round of fixes, were higher.
- **Not yet tested with real workers.** Real dictation will bring phrasings we have not seen.

## Languages

- **Full:** Hindi / Hinglish and Marathi.
- **Beta:** Bengali, Tamil, Telugu, Bhojpuri and English mix. The LLM replies in the language, but the read-back, the result and the choices are in Hindi, in the Hindi voice. Bhojpuri has no voice of its own.
- Language detection reads text only (the script and a few common words). It can be wrong on short or mixed messages; it falls back to Hindi, and the toggle overrides it.

## Voice

- **No speech-to-text in the app.** Speech-to-text is Wispr Flow's job on the worker's device. If Wispr Flow mishears, the worker sees the text and can fix it before pressing Continue.
- The agent's voice needs a Sarvam key for anything beyond the recorded demo clips; without it the browser's own voice speaks, and some browsers have no Hindi or Marathi voice.

## Privacy and storage

- Cases are stored in one SQLite file on the server, with no accounts and no analytics. That also means **no backup**: on Railway, a redeploy without a volume starts a new file.
- With keys set, the worker's words go to the LLM provider (OpenAI or OpenRouter) and the agent's lines go to Sarvam. The scripted demo makes no outside call.
- The follow-up works only in the same browser: the case id is kept in that browser's storage.
- Delete removes the row from our database. It cannot remove a WhatsApp message the worker already sent, or text a volunteer already copied.

## Cost

- The cost per case in the pitch deck is an estimate from list prices and typical turn counts, not a measured bill. Sarvam's own pages give two different text-to-speech prices, so that part is labelled [UNVERIFIED].
