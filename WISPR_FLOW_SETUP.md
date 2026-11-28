# Wispr Flow setup

PagarSaathi has **no microphone button, by design**. Its voice layer is **Wispr Flow**, which works at the operating-system level. You speak, Wispr Flow writes the words into whatever text box has focus, and PagarSaathi reads that text.

Because the app only receives text, it needs no Wispr Flow API key and no speech-to-text key.

## Mac

1. Install Wispr Flow from [wisprflow.ai](https://wisprflow.ai) and sign in.
2. In Wispr Flow settings, choose your languages: **Hindi** and **English**. Wispr Flow lists Hinglish support and can write romanised Hindi, such as "chhe din".
3. Set the dictation shortcut to **double-tap Fn**. If your version offers only press-and-hold Fn, hold Fn while you speak instead.
4. Open PagarSaathi and press **Shuru karein**. The cursor is already in the answer box.
5. **Double-tap Fn**, say your answer ("Chhe din"), then stop. The text appears in the box.
6. Press **Continue**, or the Enter key.

## iPhone

1. Install **Wispr Flow** from the App Store and sign in.
2. Go to **Settings → General → Keyboard → Keyboards → Add New Keyboard → Wispr Flow**.
3. Tap **Wispr Flow** in that list and turn on **Allow Full Access**.
4. Open PagarSaathi in Safari and tap **Shuru karein**, then tap the answer box.
5. Tap the **globe** 🌐 key and choose **Wispr Flow**.
6. Tap the **mic** and say your answer. The text appears in the box.
7. Tap **Continue**.

## Showing Wispr Flow on camera

Judges should *see* that the words come from your voice:

1. Record the whole screen, not just the browser, so Wispr Flow's on-screen indicator is in the shot when you double-tap Fn.
2. Click the answer box first; it has a white **W** and "Speak your answer" above it.
3. Double-tap Fn, speak, and pause for a second. The words appear in the box on camera, then press **Continue**.
4. On iPhone, screen-record with the Wispr Flow keyboard visible; tap its mic so the recording shows it.
5. Keep the speaker volume up so the agent's reply is heard in the recording.

## What the app does with the text

- The text can be Roman Hinglish ("saat sau"), digits ("700", "₹3,000") or Devanagari ("सात सौ"). The built-in reader handles all three with no API key.
- The agent speaks each reply: with Sarvam's Hindi voice when the server has a key, a recorded clip for the fixed lines, or the browser's own Hindi voice. A grey badge under each line says which.
- If the answer isn't clear, the agent asks again in simpler words. After two misses it suggests asking a friend for help (*needs assistance*).

## No Wispr Flow on this device?

Typing works the same way. For a demo without dictating, use `/?mode=scripted`. It fills in each answer as Wispr Flow would and presses Continue by itself.
