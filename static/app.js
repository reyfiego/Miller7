// -------------------------
// SESIÓN
// -------------------------
const SESSION_KEY = "miller_session_id"; 

// Si el usuario está logueado, forzamos nuevo session_id
let loggedIn = localStorage.getItem("miller_logged_in") === "true";
let userId = localStorage.getItem("miller_user_id"); 

let sessionId;
if (loggedIn) {
  // Siempre nuevo session_id al iniciar sesión
  sessionId = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, sessionId);
} else {
  // Invitado: usar existente o crear uno
  sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
  }
}

// -------------------------
// ELEMENTOS DEL DOM
// -------------------------
// (igual que antes, no se modifican)

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
// FUNCIONES DE UI
// -------------------------
// (igual que antes, no se modifican)

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
    console.log("Conectado al WebSocket");
    // Cargar mensajes previos desde backend
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
    try { 
      data = JSON.parse(event.data); 
    } catch { 
      data = { reply: [event.data] }; 
    }

    if (Array.isArray(data.reply)) {
      for (let i = 0; i < data.reply.length; i++) {
        const msg = data.reply[i].replace(/(\.\.\.)+/g, "…");
        if (burbujasMostradas.has(msg)) continue;

        if (i === 0) {
          addBubble("ai", msg);
        } else {
          await delay(2000); 
          addBubble("ai", msg);
        }

        burbujasMostradas.add(msg);
      }
    }
  };

  ws.onclose = () => { 
    console.log("WebSocket cerrado. Reconectando en 3s..."); 
    setTimeout(connectWS, 3000); 
  };

  ws.onerror = (err) => { 
    console.error("Error WebSocket:", err); 
    ws.close(); 
  };
}
connectWS();

function send(text) {
  addBubble("you", text);
  input.value = "";
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ 
      message: text,
      user_id: loggedIn ? userId : null
    })); 
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

function delay(ms) { 
  return new Promise(resolve => setTimeout(resolve, ms)); 
}

// -------------------------
// MICROFONO
// -------------------------
// (igual que antes, sin cambios)

// -------------------------
// LOGIN / REGISTRO
// -------------------------
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(loginForm);
  const email = formData.get("email").trim();
  const password = formData.get("password").trim();
  if (!email || !password) { 
    alert("Por favor completa todos los campos."); 
    return; 
  }

  try {
    const res = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (data.success) {
      alert("Inicio de sesión exitoso");

      // Cambiar sesión a nueva
      sessionId = crypto.randomUUID();
      localStorage.setItem(SESSION_KEY, sessionId);

      loggedIn = true;
      userId = data.user_id;
      localStorage.setItem("miller_logged_in", "true");
      localStorage.setItem("miller_user_id", userId);
      closeElement(loginPanel);

      // Reconectar WebSocket con nueva sesión
      if (ws) ws.close();
      connectWS();
    } else {
      alert(data.message || "Error en inicio de sesión");
    }
  } catch {
    alert("Error al conectar con el servidor");
  }
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(registerForm);
  const email = formData.get("email").trim();
  const password = formData.get("password").trim();
  if (!email || !password) { 
    alert("Por favor completa todos los campos."); 
    return; 
  }

  try {
    const res = await fetch("/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (data.success) {
      alert("Registro exitoso, ya puedes iniciar sesión");
      closeElement(registerPanel);
    } else {
      alert(data.message || "Error en registro");
    }
  } catch {
    alert("Error al conectar con el servidor");
  }
});
