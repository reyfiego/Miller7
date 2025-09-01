const SESSION_KEY = "miller_session_id";
let sessionId = localStorage.getItem(SESSION_KEY) || null;

const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");
const micBtn = document.getElementById("mic-btn");
const overlay = document.getElementById("voice-overlay");
const confirmBtn = document.getElementById("confirm");
const cancelBtn = document.getElementById("cancel");

// Modal info
const infoBtn = document.getElementById("info-btn");
const modal = document.getElementById("info-modal");
const closeModal = document.getElementById("close-modal");

infoBtn.addEventListener("click", () => { modal.style.display = "block"; });
closeModal.addEventListener("click", () => { modal.style.display = "none"; });
window.addEventListener("click", e => { if(e.target===modal){ modal.style.display="none"; } });

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
    if (data.session_id) { sessionId = data.session_id; localStorage.setItem(SESSION_KEY, sessionId); }
    if (data.reply) addBubble("ai", data.reply);
    else addBubble("ai", "⚠️ No entendí la respuesta del servidor.");
  } catch (err) { addBubble("ai", "❌ Error al conectar con el servidor."); console.error(err); }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (text) { send(text); input.value = ""; }
});

// Bienvenida aleatoria
async function showGreeting() {
  try {
    const res = await fetch("/greeting");
    const data = await res.json();
    if (data.greeting) addBubble("ai", data.greeting);
  } catch (err) { addBubble("ai", "¡Hola! Estoy listo para charlar contigo."); console.error(err); }
}
showGreeting();

// Micrófono y overlay
let recognition;
let currentTranscript = "";

if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = "es-ES";
  recognition.interimResults = true;

  recognition.addEventListener("result", (e) => {
    currentTranscript = e.results[0][0].transcript;
    const bars = overlay.querySelectorAll(".bar");
    bars.forEach((bar) => {
      const scale = 0.3 + Math.random();
      bar.style.height = `${scale * 40}px`;
    });
  });

  recognition.addEventListener("end", () => { micBtn.disabled = false; });

  micBtn.addEventListener("click", () => {
    overlay.style.display = "flex";
    micBtn.disabled = true;
    recognition.start();
  });

  confirmBtn.addEventListener("click", () => {
    send(currentTranscript);
    overlay.style.display = "none";
    input.value = "";
    currentTranscript = "";
  });

  cancelBtn.addEventListener("click", () => {
    overlay.style.display = "none";
    currentTranscript = "";
  });

} else {
  micBtn.disabled = true;
  micBtn.title = "Tu navegador no soporta reconocimiento de voz";
}
