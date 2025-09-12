// -------------------------
// SESIÓN
// -------------------------
const SESSION_KEY = "miller_session_id";
const LOGGED_KEY = "miller_logged_in";
const USER_ID_KEY = "miller_user_id";

let loggedIn = localStorage.getItem(LOGGED_KEY) === "true";
let userId = localStorage.getItem(USER_ID_KEY);
let sessionId;

// --- Determinar sessionId ---
if (loggedIn && userId) {
    // Usuario logeado: sesión fija por usuario
    sessionId = `user-${userId}`;
    localStorage.setItem(SESSION_KEY, sessionId);
} else {
    // Guest: generar nuevo sessionId cada refresh
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
}

// -------------------------
// ELEMENTOS DEL DOM
// -------------------------
const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");
const micBtn = document.getElementById("mic-btn");
const overlay = document.getElementById("voice-overlay");
const confirmBtn = document.getElementById("confirm");
const cancelBtn = document.getElementById("cancel");
const waveBar = overlay.querySelector(".wave-level");

const infoBtn = document.getElementById("info-btn");
const modal = document.getElementById("info-modal");
const closeModal = document.getElementById("close-modal");

const loginBtn = document.getElementById("login-btn");
const registerBtn = document.getElementById("register-btn");
const loginPanel = document.getElementById("login-panel");
const registerPanel = document.getElementById("register-panel");
const closeLogin = document.getElementById("close-login");
const closeRegister = document.getElementById("close-register");
const panelOverlay = document.getElementById("panel-overlay");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");

// -------------------------
// UI FUNCTIONS
// -------------------------
function openElement(element) {
    element.classList.add("active");
    element.classList.remove("closing");
    if (element === loginPanel || element === registerPanel) panelOverlay.classList.add("active");
}

function closeElement(element) {
    element.classList.add("closing");
    setTimeout(() => {
        element.classList.remove("active", "closing");
        if (element === loginPanel || element === registerPanel) panelOverlay.classList.remove("active");
    }, 300);
}

loginBtn.addEventListener("click", () => { 
    openElement(loginPanel); 
    registerPanel.classList.remove("active"); 
});
registerBtn.addEventListener("click", () => { 
    openElement(registerPanel); 
    loginPanel.classList.remove("active"); 
});
closeLogin.addEventListener("click", () => closeElement(loginPanel));
closeRegister.addEventListener("click", () => closeElement(registerPanel));
panelOverlay.addEventListener("click", () => { 
    closeElement(loginPanel); 
    closeElement(registerPanel); 
});

infoBtn.addEventListener("click", () => openElement(modal));
closeModal.addEventListener("click", () => closeElement(modal));
window.addEventListener("click", (e) => { 
    if (e.target === modal) closeElement(modal); 
});

// -------------------------
// CHAT
// -------------------------
function addBubble(sender, text) {
    const bubble = document.createElement("div");
    bubble.className = `bubble ${sender}`;
    bubble.innerHTML = `<strong>${sender === "you" ? "Tú" : "Miller"}:</strong> ${escapeHtml(text)}`;
    chatEl.appendChild(bubble);
    chatEl.scrollTop = chatEl.scrollHeight;
}

function escapeHtml(str) {
    return str.replace(/[&<>"']/g, (s) => ({ 
        '&': '&amp;', 
        '<': '&lt;', 
        '>': '&gt;', 
        '"': '&quot;', 
        "'": '&#039;' 
    }[s]));
}

let ws;
let burbujasMostradas = new Set();

// -------------------------
// WEBSOCKET
// -------------------------
function connectWS() {
    if (ws && ws.readyState !== WebSocket.CLOSED) return;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${protocol}://${window.location.host}/ws/chat/${sessionId}`);

    ws.onopen = async () => {
        console.log("Conectado al WebSocket con session_id:", sessionId);

        // Cargar historial previo
        try {
            const res = await fetch(`/session/${sessionId}/messages`);
            const data = await res.json();
            if (Array.isArray(data.messages)) {
                data.messages.forEach(msg => {
                    const sender = msg.sender === "user" ? "you" : "ai";
                    addBubble(sender, msg.content);
                    burbujasMostradas.add(msg.content);
                });
            }
        } catch (err) {
            console.warn("No se pudieron cargar mensajes previos:", err);
        }
    };

    ws.onmessage = async (event) => {
        let data;
        try { data = JSON.parse(event.data); } 
        catch { data = { reply: [event.data] }; }

        if (Array.isArray(data.reply)) {
            for (let i = 0; i < data.reply.length; i++) {
                const msg = data.reply[i].replace(/(\.\.\.)+/g, "…");
                if (burbujasMostradas.has(msg)) continue;
                if (i === 0) addBubble("ai", msg);
                else await delay(2000), addBubble("ai", msg);
                burbujasMostradas.add(msg);
            }
        }
    };

    ws.onclose = () => setTimeout(connectWS, 3000);
    ws.onerror = (err) => { console.error("Error WS:", err); ws.close(); };
}

connectWS();

function send(text) {
    addBubble("you", text);
    input.value = "";
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ message: text, user_id: loggedIn ? userId : null }));
    } else {
        addBubble("ai", "❌ No hay conexión con el servidor. Intentando reconectar...");
        reconnectWS();
    }
}

function reconnectWS() {
    if (!ws || ws.readyState === WebSocket.CLOSED) connectWS();
}

form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (text) send(text);
});

function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

// -------------------------
// MICROFONO
// -------------------------
let recognition;
let currentTranscript = "";
if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = "es-ES";
    recognition.interimResults = true;

    recognition.addEventListener("result", (e) => {
        currentTranscript = e.results[0][0].transcript;
        waveBar.style.width = Math.min(100, Math.random() * 100) + "%";
    });

    recognition.addEventListener("end", () => { micBtn.disabled = false; waveBar.style.width = "0%"; });

    micBtn.addEventListener("click", () => { overlay.style.display = "flex"; micBtn.disabled = true; recognition.start(); });
    confirmBtn.addEventListener("click", () => { if (currentTranscript.trim()) send(currentTranscript); overlay.style.display = "none"; currentTranscript = ""; waveBar.style.width = "0%"; });
    cancelBtn.addEventListener("click", () => { overlay.style.display = "none"; currentTranscript = ""; waveBar.style.width = "0%"; });
} else {
    micBtn.disabled = true;
    micBtn.title = "Tu navegador no soporta reconocimiento de voz";
}

// -------------------------
// LOGIN / REGISTRO
// -------------------------
// Al hacer login exitoso
loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(loginForm);
    const email = formData.get("email").trim();
    const password = formData.get("password").trim();
    if (!email || !password) return alert("Completa todos los campos.");

    try {
        const res = await fetch("/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (data.success) {
            loggedIn = true;
            userId = data.user_id;

            // Guardar credenciales
            localStorage.setItem(LOGGED_KEY, "true");
            localStorage.setItem(USER_ID_KEY, userId);

            // ⚡ Cambiar sessionId a fijo de usuario y reconectar WS
            sessionId = `user-${userId}`;
            localStorage.setItem(SESSION_KEY, sessionId);

            ws.close();   // cerrar conexión anterior
            connectWS();  // reconectar con sessionId fijo

            closeElement(loginPanel);
        } else {
            alert(data.message || "Error en inicio de sesión");
        }
    } catch {
        alert("Error al conectar con el servidor");
    }