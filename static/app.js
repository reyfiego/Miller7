const SESSION_KEY = "miller_session_id";
let sessionId = localStorage.getItem(SESSION_KEY) || null;

const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");

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

    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem(SESSION_KEY, sessionId);
    }

    if (data.reply) {
      addBubble("ai", data.reply);
      // speakReply(data.reply); // Desactivado para que no hable, solo texto
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
// Botón de micrófono dinámico
// -----------------------
const micBtn = document.createElement("button");
micBtn.textContent = "🎤";
micBtn.className = "btn-mic";
document.querySelector(".composer").insertBefore(micBtn, document.getElementById("send"));

let recognition;
if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = "es-ES";
  recognition.interimResults = false;

  recognition.addEventListener("result", (e) => {
    const transcript = e.results[0][0].transcript;
    input.value = transcript;
    send(transcript);
  });

  recognition.addEventListener("end", () => {
    micBtn.disabled = false;
  });

  micBtn.addEventListener("click", () => {
    micBtn.disabled = true;
    recognition.start();
  });
} else {
  micBtn.disabled = true;
  micBtn.title = "Tu navegador no soporta reconocimiento de voz";
}
