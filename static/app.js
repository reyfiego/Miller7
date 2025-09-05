// -------------------------
// SESIÓN
// -------------------------
const SESSION_KEY = "miller_session_id";
let sessionId = localStorage.getItem(SESSION_KEY);
if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, sessionId);
}
let loggedIn = localStorage.getItem("miller_logged_in") === "true";

// -------------------------
// ELEMENTOS DOM
// -------------------------
const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");
const micBtn = document.getElementById("mic-btn");
const overlay = document.getElementById("voice-overlay");
const confirmBtn = document.getElementById("confirm");
const cancelBtn = document.getElementById("cancel");
const waveBar = overlay.querySelector(".wave-level");

// Modal info
const infoBtn = document.getElementById("info-btn");
const modal = document.getElementById("info-modal");
const closeModal = document.getElementById("close-modal");

// Paneles login & registro
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
// VARIABLES CHAT
// -------------------------
let awaitingUser = false;
let consecutiveBubbles = 0;
const MAX_CONSECUTIVE_BUBBLES = 1; // Evita múltiples burbujas automáticas
let autoMessageTimeout = null;

// -------------------------
// FUNCIONES UI
// -------------------------
function addBubble(sender, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender}`;
  bubble.innerHTML = `<strong>${sender === "you" ? "Tú" : "Miller"}:</strong> ${escapeHtml(text)}`;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (s) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[s]));
}

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

// -------------------------
// LOGIN & REGISTRO
// -------------------------
loginBtn.addEventListener("click", () => { openElement(loginPanel); registerPanel.classList.remove("active"); });
registerBtn.addEventListener("click", () => { openElement(registerPanel); loginPanel.classList.remove("active"); });
closeLogin.addEventListener("click", () => closeElement(loginPanel));
closeRegister.addEventListener("click", () => closeElement(registerPanel));
panelOverlay.addEventListener("click", () => { closeElement(loginPanel); closeElement(registerPanel); });

loginForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const formData = new FormData(loginForm);
  const email = formData.get("email").trim();
  const password = formData.get("password").trim();
  if (!email || !password) { alert("Por favor completa todos los campos."); return; }

  fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      alert("Inicio de sesión exitoso");
      loggedIn = true;
      localStorage.setItem("miller_logged_in", "true");
      closeElement(loginPanel);
    } else alert(data.message || "Error en inicio de sesión");
  })
  .catch(() => alert("Error al conectar con el servidor"));
});

registerForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const formData = new FormData(registerForm);
  const email = formData.get("email").trim();
  const password = formData.get("password").trim();
  if (!email || !password) { alert("Por favor completa todos los campos."); return; }

  fetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      alert("Registro exitoso, ya puedes iniciar sesión");
      closeElement(registerPanel);
    } else alert(data.message || "Error en registro");
  })
  .catch(() => alert("Error al conectar con el servidor"));
});

// -------------------------
// MODAL INFO
// -------------------------
infoBtn.addEventListener("click", () => openElement(modal));
closeModal.addEventListener("click", () => closeElement(modal));
window.addEventListener("click", (e) => { if (e.target === modal) closeElement(modal); });

// -------------------------
// ENVÍO DE MENSAJE
// -------------------------
function send(text) {
  addBubble("you", text);
  input.value = "";
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ message: text }));
    awaitingUser = true;
    consecutiveBubbles = 0;
    clearTimeout(autoMessageTimeout);
    startAutoMessageTimer();
  } else addBubble("ai", "❌ No hay conexión con el servidor.");
}

function startAutoMessageTimer() {
  clearTimeout(autoMessageTimeout);
  autoMessageTimeout = setTimeout(() => {
    if (awaitingUser && consecutiveBubbles < MAX_CONSECUTIVE_BUBBLES) {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ auto: true }));
    }
  }, 15000); // 15s sin respuesta
}

// -------------------------
// WEBSOCKET
// -------------------------
let ws;
function connectWS() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${protocol}://${window.location.host}/ws/chat/${sessionId}`);

  ws.onopen = () => console.log("Conectado al WebSocket");

  ws.onmessage = async (event) => {
    let data;
    try { data = JSON.parse(event.data); } 
    catch { data = { reply: [event.data] }; }

    if (data.reply) {
      awaitingUser = false;
      consecutiveBubbles = 0;
      clearTimeout(autoMessageTimeout);

      for (let b of data.reply) {
        await delay(500 + Math.random() * 800);
        addBubble("ai", b);
        consecutiveBubbles++;
      }

      startAutoMessageTimer();
    }
  };

  ws.onclose = () => setTimeout(connectWS, 3000);
  ws.onerror = (err) => { console.error("Error WebSocket:", err); ws.close(); };
}
connectWS();

// -------------------------
// FORM SUBMIT
// -------------------------
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (text) send(text);
});

// -------------------------
// UTILIDADES
// -------------------------
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
    const level = Math.min(100, Math.random() * 100);
    waveBar.style.width = level + "%";
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
// DETECTAR ACTIVIDAD USUARIO
// -------------------------
function detectUserReturn() { awaitingUser = false; consecutiveBubbles = 0; clearTimeout(autoMessageTimeout); }
window.addEventListener("mousemove", detectUserReturn);
window.addEventListener("keydown", detectUserReturn);
