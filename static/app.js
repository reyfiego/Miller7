const SESSION_KEY = "miller_session_id";
let sessionId = localStorage.getItem(SESSION_KEY) || null;

const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");
const micBtn = document.getElementById("mic");
const overlay = document.getElementById("voice-overlay");
const confirmBtn = document.getElementById("confirm");
const cancelBtn = document.getElementById("cancel");

const infoBtn = document.getElementById("info-btn");
const modal = document.getElementById("info-modal");
const closeModal = document.getElementById("close-modal");

infoBtn.addEventListener("click", () => { modal.style.display = "block"; });
closeModal.addEventListener("click", () => { modal.style.display = "none"; });
window.addEventListener("click", e => { if(e.target===modal){ modal.style.display="none"; } });

function addBubble(sender, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender}`;
  bubble.innerHTML = `<strong>${sender === "you" ? "Tú" : "Miller"}:</strong> ${text}`;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
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

form.addEventListener("submit", e => {
  e.preventDefault();
  const text = input.value.trim();
  if (text) {
    send(text);
    input.value = "";
  }
});

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
// Micrófono con overlay de confirmación
// -----------------------
let recognition;
let tempTranscript = "";

if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = "es-ES";
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    tempTranscript = "";
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      const transcript = event.results[i][0].transcript;
      tempTranscript += transcript + " ";
    }
  };

  recognition.onend = () => {
    micBtn.disabled = false;
  };

  micBtn.addEventListener("click", () => {
    micBtn.disabled = true;
    overlay.style.display = "flex";
    tempTranscript = "";
    recognition.start();
  });

  confirmBtn.onclick = () => {
    overlay.style.display = "none";
    recognition.stop();
    if (tempTranscript.trim() !== "") {
      input.value = tempTranscript.trim();
      send(input.value);
      input.value = "";
    }
  };

  cancelBtn.onclick = () => {
    overlay.style.display = "none";
    recognition.stop();
    tempTranscript = "";
  };

} else {
  micBtn.disabled = true;
  micBtn.title = "Tu navegador no soporta reconocimiento de voz";
}
