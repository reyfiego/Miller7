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
// COLA DE MENSAJES CON FILTRADO
// -------------------------
let messageQueue = [];
let processingQueue = false;
const MESSAGE_DELAY = 1300; // ms entre burbujas
let lastMessage = "";

function isRelevant(msg) {
  msg = msg.trim();
  if (msg.length < 5) return false;            // demasiado corto
  if (msg === lastMessage) return false;       // repetitivo
  return true;
}

function processQueue() {
  if (processingQueue || messageQueue.length === 0) return;
  processingQueue = true;
  const next = messageQueue.shift();
  addBubble("ai", next);
  lastMessage = next;
  setTimeout(() => {
    processingQueue = false;
    processQueue();
  }, MESSAGE_DELAY + Math.random() * 600); // pequeño extra aleatorio
}

function queueMessage(text) {
  if (isRelevant(text)) messageQueue.push(text);
  processQueue();
}

function send(text) {
  addBubble("you", text);
  input.value = "";
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ message: text }));
  } else {
    queueMessage("❌ No hay conexión con el servidor. Intentando reconectar...");
    reconnectWS();
  }
}

// -------------------------
// WEB SOCKET
// -------------------------
let ws;
let firstInteraction = true; // Control inicial de intensidad

function connectWS() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${protocol}://${window.location.host}/ws/chat/${sessionId}`);

  ws.onopen = () => console.log("Conectado al WebSocket");

  ws.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      // Limpiar headers tipo <|header_start|>...
      let cleaned = event.data.replace(/<\|.*?\|>/g, "").trim();
      cleaned = cleaned.replace(/^"+|"+$/g, "");
      data = { reply: [cleaned] };
    }

    if (data.reply) {
      data.reply.forEach((msg) => {
        // Control de intensidad inicial
        if (firstInteraction) {
          // recortar si es demasiado largo
          if (msg.length > 120) msg = msg.slice(0, 120) + "...";
          // espaciar más al inicio
          setTimeout(() => queueMessage(msg), Math.random() * 800);
        } else {
          queueMessage(msg);
        }
      });
      firstInteraction = false;
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
