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
// FUNCIONES DE UI
// -------------------------
function openElement(element) {
  element.classList.add("active");
  element.classList.remove("closing");
  if (element === loginPanel || element === registerPanel) {
    panelOverlay.classList.add("active");
  }
}

function closeElement(element) {
  element.classList.add("closing");
  setTimeout(() => {
    element.classList.remove("active", "closing");
    if (element === loginPanel || element === registerPanel) {
      panelOverlay.classList.remove("active");
    }
  }, 300);
}

// -------------------------
// PANEL LOGIN & REGISTRO
// -------------------------
loginBtn.addEventListener("click", () => { openElement(loginPanel); registerPanel.classList.remove("active"); });
registerBtn.addEventListener("click", () => { openElement(registerPanel); loginPanel.classList.remove("active"); });
closeLogin.addEventListener("click", () => closeElement(loginPanel));
closeRegister.addEventListener("click", () => closeElement(registerPanel));
panelOverlay.addEventListener("click", () => { closeElement(loginPanel); closeElement(registerPanel); });

// -------------------------
// MODAL INFO
// -------------------------
infoBtn.addEventListener("click", () => openElement(modal));
closeModal.addEventListener("click", () => closeElement(modal));
window.addEventListener("click", (e) => { if (e.target === modal) closeElement(modal); });

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
  return str.replace(/[&<>"']/g, (s) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[s]));
}

// -------------------------
// CONTROL DE HILO
// -------------------------
let awaitingUser = false;      // Bloquea mensajes hasta que el usuario responda
let autoMessageTimeout = null; // Temporizador de mensajes automáticos

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
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      let cleaned = event.data.replace(/<\|.*?\|>/g, "").trim();
      cleaned = cleaned.replace(/^"+|"+$/g, "");
      data = { reply: [cleaned] };
    }

    if (data.reply && !awaitingUser) {
      awaitingUser = true; // Bloquea hasta respuesta del usuario
      clearTimeout(autoMessageTimeout);

      const bubbles = data.reply.slice(0, 3); // máximo 3 burbujas
      bubbles.forEach((b, i) => {
        const delayTime = 300 + Math.random() * 400 + i * 250; // retardo variable y natural
        setTimeout(() => addBubble("ai", b), delayTime);
      });

      // Desbloquea a Miller después de 15s de inactividad
      autoMessageTimeout = setTimeout(() => { awaitingUser = false; }, 15000);
    } else if (typeof data === "string") {
      addBubble("ai", data);
    }
  };

  ws.onclose = () => { console.log("WebSocket cerrado. Reconectando en 3s..."); setTimeout(connectWS, 3000); };
  ws.onerror = (err) => { console.error("Error WebSocket:", err); ws.close(); };
}
connectWS();

function reconnectWS() {
  if (!ws || ws.readyState === WebSocket.CLOSED) connectWS();
}

// -------------------------
// ENVÍO DE MENSAJE
// -------------------------
function send(text) {
  addBubble("you", text);
  input.value = "";
  awaitingUser = false; // Usuario respondió, desbloquea a Miller

  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ message: text }));
  } else {
    addBubble("ai", "❌ No hay conexión con el servidor. Intentando reconectar...");
    reconnectWS();
  }
}

// -------------------------
// FORMULARIO
// -------------------------
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (text) send(text);
});

// -------------------------
// RETARDO ENTRE BURBUJAS
// -------------------------
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

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
// LOGIN
// -------------------------
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

// -------------------------
// REGISTRO
// -------------------------
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
