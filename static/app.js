const SESSION_KEY = "miller_session_id";
let sessionId = localStorage.getItem(SESSION_KEY) || null;

const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");
const micBtn = document.getElementById("mic-btn");
const overlay = document.getElementById("voice-overlay");
const confirmBtn = document.getElementById("confirm");
const cancelBtn = document.getElementById("cancel");
const waveBar = overlay.querySelector(".wave-level");

// --- Modal info ---
const infoBtn = document.getElementById("info-btn");
const modal = document.getElementById("info-modal");
const closeModal = document.getElementById("close-modal");

// --- Paneles Login & Registro ---
const loginBtn = document.getElementById("login-btn");
const registerBtn = document.getElementById("register-btn");
const loginPanel = document.getElementById("login-panel");
const registerPanel = document.getElementById("register-panel");
const closeLogin = document.getElementById("close-login");
const closeRegister = document.getElementById("close-register");
const panelOverlay = document.getElementById("panel-overlay");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");

// Función para abrir panel o modal con animación
function openElement(element) {
  element.classList.add("active");
  element.classList.remove("closing");
  if (element === loginPanel || element === registerPanel) {
    panelOverlay.classList.add("active");
  }
}

// Función para cerrar panel o modal con animación
function closeElement(element) {
  element.classList.add("closing");
  setTimeout(() => {
    element.classList.remove("active", "closing");
    if (element === loginPanel || element === registerPanel) {
      panelOverlay.classList.remove("active");
    }
  }, 300); // Duración de la animación en ms (debe coincidir con CSS)
}

// Abrir panel login
loginBtn.addEventListener("click", () => {
  openElement(loginPanel);
  registerPanel.classList.remove("active");
});

// Abrir panel registro
registerBtn.addEventListener("click", () => {
  openElement(registerPanel);
  loginPanel.classList.remove("active");
});

// Cerrar paneles con botones
closeLogin.addEventListener("click", () => closeElement(loginPanel));
closeRegister.addEventListener("click", () => closeElement(registerPanel));

// Cerrar paneles al hacer click fuera
panelOverlay.addEventListener("click", () => {
  closeElement(loginPanel);
  closeElement(registerPanel);
});

// --- Modal info ---
infoBtn.addEventListener("click", () => openElement(modal));
closeModal.addEventListener("click", () => closeElement(modal));
window.addEventListener("click", (e) => {
  if (e.target === modal) closeElement(modal);
});

// --- Chat ---
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

async function send(text) {
  addBubble("you", text);
  input.value = "";
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    const data = await res.json();
    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem(SESSION_KEY, sessionId);
    }
    if (data.reply) {
      addBubble("ai", data.reply);
    } else {
      addBubble("ai", "⚠️ No entendí la respuesta del servidor.");
    }
  } catch (err) {
    addBubble("ai", "❌ Error al conectar con el servidor.");
    console.error(err);
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (text) send(text);
});

// --- Mensaje de bienvenida ---
async function showGreeting() {
  try {
    const res = await fetch("/greeting");
    const data = await res.json();
    if (data.greeting) addBubble("ai", data.greeting);
  } catch (err) {
    addBubble("ai", "¡Hola! Estoy listo para charlar contigo.");
  }
}
showGreeting();

// --- Micrófono con barra horizontal ---
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

  recognition.addEventListener("end", () => {
    micBtn.disabled = false;
    waveBar.style.width = "0%";
  });

  micBtn.addEventListener("click", () => {
    overlay.style.display = "flex";
    micBtn.disabled = true;
    recognition.start();
  });

  confirmBtn.addEventListener("click", () => {
    if (currentTranscript.trim()) send(currentTranscript);
    overlay.style.display = "none";
    currentTranscript = "";
    waveBar.style.width = "0%";
  });

  cancelBtn.addEventListener("click", () => {
    overlay.style.display = "none";
    currentTranscript = "";
    waveBar.style.width = "0%";
  });
} else {
  micBtn.disabled = true;
  micBtn.title = "Tu navegador no soporta reconocimiento de voz";
}

// --- Manejo de formularios Login y Registro ---
loginForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const formData = new FormData(loginForm);
  const email = formData.get("email").trim();
  const password = formData.get("password").trim();

  if (!email || !password) {
    alert("Por favor completa todos los campos.");
    return;
  }

  fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.success) {
        alert("Inicio de sesión exitoso");
        closeElement(loginPanel);
        // Aquí puedes guardar sesión, actualizar UI, etc.
      } else {
        alert(data.message || "Error en inicio de sesión");
      }
    })
    .catch(() => alert("Error al conectar con el servidor"));
});

registerForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const formData = new FormData(registerForm);
  const email = formData.get("email").trim();
  const password = formData.get("password").trim();

  if (!email || !password) {
    alert("Por favor completa todos los campos.");
    return;
  }

  fetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.success) {
        alert("Registro exitoso, ya puedes iniciar sesión");
        closeElement(registerPanel);
      } else {
        alert(data.message || "Error en registro");
      }
    })
    .catch(() => alert("Error al conectar con el servidor"));
});