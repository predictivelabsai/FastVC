/* Voice mode — mic ↔ x.ai realtime agent over /ws/voice (PCM16 mono @ 24kHz). */
(() => {
    const RATE = 24000;
    const $ = (s) => document.querySelector(s);

    let ws = null, active = false;
    let micCtx = null, playCtx = null, stream = null, node = null, srcNode = null, zeroGain = null;
    let nextTime = 0, playing = [];
    let asstBubble = null;      // live assistant transcript bubble
    let statusEl = null;

    // ── UI ──────────────────────────────────────────────────────────────
    function setStatus(state, label) {
        const p = $("#voice-panel");
        if (p) p.setAttribute("data-state", state);
        if (statusEl) statusEl.textContent = label;
        const btn = $("#voice-btn");
        if (btn) btn.classList.toggle("active", active);
    }
    function showPanel() {
        if ($("#voice-panel")) return;
        const p = document.createElement("div");
        p.id = "voice-panel";
        p.className = "voice-panel";
        p.setAttribute("data-state", "connecting");
        p.innerHTML =
            '<span class="voice-orb"></span>' +
            '<span class="voice-status" id="voice-status">Connecting…</span>' +
            '<button class="voice-stop" id="voice-stop">End voice</button>';
        const form = $(".chat-form");
        if (form && form.parentElement) form.parentElement.insertBefore(p, form);
        statusEl = $("#voice-status");
        $("#voice-stop").onclick = stopVoice;
    }
    function hidePanel() {
        const p = $("#voice-panel");
        if (p) p.remove();
        statusEl = null;
    }

    // ── Transcript bubbles (self-contained; mirrors chat.js markup) ───────
    function addBubble(role, text) {
        const wrap = document.createElement("div");
        wrap.className = `msg msg-${role}`;
        const b = document.createElement("div");
        b.className = "msg-bubble";
        b.textContent = text || "";
        wrap.appendChild(b);
        const m = $("#messages");
        if (m) { m.appendChild(wrap); m.scrollTop = m.scrollHeight; }
        return b;
    }

    // ── Audio helpers ─────────────────────────────────────────────────────
    function floatToPCM16(f32) {
        const out = new Int16Array(f32.length);
        for (let i = 0; i < f32.length; i++) {
            let s = Math.max(-1, Math.min(1, f32[i]));
            out[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return out;
    }
    function downsample(f32, inRate) {
        if (inRate === RATE) return floatToPCM16(f32);
        const ratio = inRate / RATE, outLen = Math.floor(f32.length / ratio);
        const out = new Int16Array(outLen);
        for (let i = 0; i < outLen; i++) {
            const start = Math.floor(i * ratio), end = Math.floor((i + 1) * ratio);
            let sum = 0, c = 0;
            for (let j = start; j < end && j < f32.length; j++) { sum += f32[j]; c++; }
            let s = c ? sum / c : (f32[start] || 0);
            s = Math.max(-1, Math.min(1, s));
            out[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return out;
    }
    function b64FromInt16(int16) {
        const bytes = new Uint8Array(int16.buffer);
        let bin = "";
        for (let i = 0; i < bytes.length; i += 0x8000)
            bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
        return btoa(bin);
    }
    function playPCM16(b64) {
        if (!playCtx) return;
        const bin = atob(b64), bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        const int16 = new Int16Array(bytes.buffer), f32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) f32[i] = int16[i] / 0x8000;
        const buf = playCtx.createBuffer(1, f32.length, RATE);
        buf.getChannelData(0).set(f32);
        const s = playCtx.createBufferSource();
        s.buffer = buf; s.connect(playCtx.destination);
        const now = playCtx.currentTime;
        if (nextTime < now) nextTime = now;
        s.start(nextTime); nextTime += buf.duration;
        s.onended = () => { playing = playing.filter((x) => x !== s); };
        playing.push(s);
    }
    function stopPlayback() {
        playing.forEach((s) => { try { s.stop(); } catch (e) {} });
        playing = []; nextTime = 0;
    }

    // ── Session lifecycle ─────────────────────────────────────────────────
    async function startVoice() {
        if (active) return;
        dismissHint();
        const wh = $("#welcome-hero"); if (wh) wh.style.display = "none";
        showPanel();
        setStatus("connecting", "Requesting microphone…");
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
            });
        } catch (e) {
            setStatus("error", "Microphone blocked — allow access and tap the mic again");
            setTimeout(hidePanel, 3000);
            return;
        }
        active = true;
        micCtx = new (window.AudioContext || window.webkitAudioContext)();
        playCtx = new (window.AudioContext || window.webkitAudioContext)();
        try { await micCtx.resume(); await playCtx.resume(); } catch (e) {}

        const proto = location.protocol === "https:" ? "wss" : "ws";
        ws = new WebSocket(`${proto}://${location.host}/ws/voice`);
        ws.onopen = () => setStatus("listening", "Listening…");
        ws.onclose = () => { if (active) stopVoice(); };
        ws.onerror = () => setStatus("error", "Connection error");
        ws.onmessage = (ev) => handle(JSON.parse(ev.data));

        srcNode = micCtx.createMediaStreamSource(stream);
        node = micCtx.createScriptProcessor(4096, 1, 1);
        zeroGain = micCtx.createGain(); zeroGain.gain.value = 0;
        srcNode.connect(node); node.connect(zeroGain); zeroGain.connect(micCtx.destination);
        node.onaudioprocess = (e) => {
            if (!ws || ws.readyState !== 1) return;
            const pcm = downsample(e.inputBuffer.getChannelData(0), micCtx.sampleRate);
            ws.send(JSON.stringify({ type: "audio", audio: b64FromInt16(pcm) }));
        };
    }

    function stopVoice() {
        active = false;
        try { node && node.disconnect(); } catch (e) {}
        try { srcNode && srcNode.disconnect(); } catch (e) {}
        try { stream && stream.getTracks().forEach((t) => t.stop()); } catch (e) {}
        stopPlayback();
        try { micCtx && micCtx.close(); } catch (e) {}
        try { playCtx && playCtx.close(); } catch (e) {}
        try { ws && ws.close(); } catch (e) {}
        ws = micCtx = playCtx = stream = node = srcNode = null;
        asstBubble = null;
        hidePanel();
        const btn = $("#voice-btn"); if (btn) btn.classList.remove("active");
    }

    function handle(m) {
        switch (m.type) {
            case "ready": setStatus("listening", "Listening…"); break;
            case "speech_started": stopPlayback(); setStatus("listening", "Listening…"); break;
            case "speech_stopped": setStatus("thinking", "Thinking…"); break;
            case "user_transcript":
                if (m.text) addBubble("user", m.text);
                asstBubble = null;
                break;
            case "assistant_delta":
                if (!asstBubble) asstBubble = addBubble("assistant", "");
                asstBubble.textContent += m.text || "";
                { const mm = $("#messages"); if (mm) mm.scrollTop = mm.scrollHeight; }
                setStatus("speaking", "Speaking…");
                break;
            case "audio": playPCM16(m.audio); break;
            case "assistant_done": asstBubble = null; break;
            case "done": setStatus("listening", "Listening…"); break;
            case "error":
                setStatus("error", "Voice error");
                addBubble("assistant", "Voice error: " + (m.message || "unknown"));
                break;
        }
    }

    // ── First-time hint near the mic ──────────────────────────────────────
    function dismissHint() {
        const h = $("#voice-hint");
        if (h) h.remove();
        try { localStorage.setItem("fastvc_voice_hint", "1"); } catch (e) {}
    }
    function maybeShowHint() {
        try { if (localStorage.getItem("fastvc_voice_hint")) return; } catch (e) {}
        if (!$("#voice-btn")) return;    // voice disabled server-side
        const form = $(".chat-form");
        if (!form || !form.parentElement) return;
        const h = document.createElement("div");
        h.id = "voice-hint";
        h.className = "voice-hint";
        h.innerHTML =
            '<span class="voice-hint-ic">🎤</span>' +
            '<span><strong>New — talk to your VC squad.</strong> Tap the mic to start a voice ' +
            'chat (your browser will ask to use the microphone).</span>' +
            '<button class="voice-hint-x" aria-label="Dismiss">&times;</button>';
        form.parentElement.insertBefore(h, form);
        h.querySelector(".voice-hint-x").onclick = dismissHint;
        setTimeout(() => { const x = $("#voice-hint"); if (x) x.remove(); }, 15000);
    }

    window.toggleVoice = () => { active ? stopVoice() : startVoice(); };

    if (document.readyState !== "loading") maybeShowHint();
    else document.addEventListener("DOMContentLoaded", maybeShowHint);
})();
