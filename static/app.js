const SESSION_KEY = "miller_session_id";
let sessionId = localStorage.getItem(SESSION_KEY) || null;

const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");
const micBtn = document.getElementById("mic-btn");
const voiceOverlay = document.getElementById("voice-overlay");
const confirmBtn = document.getElementById("confirm");
const cancelBtn = document.getElementById("cancel");

// Modal info
const infoBtn = document.getElementById("info-btn");
const modal = document.getElementById("info-modal");
const closeModal = document.getElementById("close-modal");

infoBtn.addEventListener("click", () => { modal.style.display = "block"; });
closeModal.addEventListener("click", () => { modal.style.display = "none"; });
window.addEventListener("click", e => { if(e.target===modal){ modal.style.display="none"; } });

// Funciones chat
function addBubble(sender, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender}`;
  bubble.innerHTML = `<strong>${sender === "you" ? "Tú" : "Miller"}:</strong> ${escapeHtml(text)}`;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[s]));
}

async function send(text) {
  addBubble("you", text);

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId })
    });

    const data = await res.json();

    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem(SESSION_KEY, sessionId);
    }

    if (data.reply) addBubble("ai", data.reply);
    else addBubble("ai", "⚠️ No entendí la respuesta del servidor.");

  } catch (err) {
    addBubble("ai", "❌ Error al conectar con el servidor.");
    console.error(err);
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (text) {
    send(text);
    input.value = "";
  }
});

// Bienvenida aleatoria
async function showGreeting() {
  try {
    const res = await fetch("/greeting");
    const data = await res.json();
    if (data.greeting) addBubble("ai", data.greeting);
  } catch (err) {
    addBubble("ai", "¡Hola! Estoy listo para charlar contigo.");
    console.error(err);
  }
}
showGreeting();

// -----------------------
// Micrófono con overlay
// -----------------------
let recognition;
if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = "es-ES";
  recognition.interimResults = true;

  micBtn.addEventListener("click", () => {
    micBtn.disabled = true;
    voiceOverlay.style.display = "flex";
    recognition.start();
  });

  recognition.addEventListener("result", (e) => {
    // No se escribe directamente en input
    const transcript = e.results[0][0].transcript;
    // Aquí podrías animar la barra de voz según e.results[0][0].confidence
  });

  recognition.addEventListener("end", () => {
    micBtn.disabled = false;
  });

  confirmBtn.addEventListener("click", () => {
    const transcript = recognition.results[0][0].transcript;
    input.value = transcript;
    send(transcript);
    voiceOverlay.style.display = "none";
  });

  cancelBtn.addEventListener("click", () => {
    voiceOverlay.style.display = "none";
  });
} else {
  micBtn.disabled = true;
  micBtn.title = "Tu navegador no soporta reconocimiento de voz";
}
