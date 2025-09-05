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

// Paneles login & registro
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");

// -------------------------
// UI
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
// WEB SOCKET CON COLA Y TURNO
// -------------------------
let ws;
let messageQueue = [];
let userCanRespond = true; // al inicio espera mensaje del usuario

function connectWS() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${protocol}://${window.location.host}/ws/chat/${sessionId}`);

  ws.onopen = () => console.log("Conectado al WebSocket");

  ws.onmessage = (event) => {
    let newMessages = [];
    try {
      const data = JSON.parse(event.data);
      if (data.reply) newMessages = data.reply;
    } catch {
      // Si no es JSON válido, lo tomamos como mensaje crudo
      newMessages = [event.data.trim()];
    }

    messageQueue.push(...newMessages);
    processQueue();
  };

  ws.onclose = () => { console.log("WebSocket cerrado. Reconectando en 3s..."); setTimeout(connectWS, 3000); };
  ws.onerror = (err) => { console.error("Error WebSocket:", err); ws.close(); };
}

function processQueue() {
  if (userCanRespond || messageQueue.length === 0) return;

  const msg = messageQueue.shift();

  // Delay opcional para dar sensación humana
  setTimeout(() => {
    addBubble("ai", msg);
    processQueue(); // procesa siguiente mensaje de la cola si hay
  }, 500 + Math.random() * 500); // 0.5s a 1s aleatorio
}

function send(text) {
  if (!text.trim()) return;
  addBubble("you", text);
  input.value = "";

  userCanRespond = false; // bloquea hasta que Miller responda

  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ message: text }));
  } else {
    addBubble("ai", "❌ No hay conexión con el servidor. Intentando reconectar...");
    if (!ws || ws.readyState === WebSocket.CLOSED) connectWS();
  }
}

connectWS();

// -------------------------
// ENVÍO DE MENSAJE
// -------------------------
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (text) send(text);
});

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
    } else alert(data.message || "Error en registro");
  })
  .catch(() => alert("Error al conectar con el servidor"));
});
