// Guardamos/recuperamos un session_id en localStorage para mantener contexto
const SESSION_KEY = "miller_session_id";
let sessionId = localStorage.getItem(SESSION_KEY) || null;

const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");

function addBubble(sender, text, type = "reply", url = null) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender}`;
  if (type === "link" && url) {
    bubble.innerHTML = `<strong>${sender === "you" ? "Tú" : "Miller"}:</strong> <a href="${url}" target="_blank" rel="noopener">${text}</a>`;
  } else {
    bubble.innerHTML = `<strong>${sender === "you" ? "Tú" : "Miller"}:</strong> ${escapeHtml(text)}`;
  }
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
    } else {
      addBubble("ai", "⚠️ No entendí la respuesta del servidor.");
    }

  } catch (err) {
    addBubble("ai", "❌ Error al conectar con el servidor.");
    console.error(err);
  }
}

// 🚀 Aquí evitamos que el formulario refresque la página
form.addEventListener("submit", (e) => {
  e.preventDefault(); // <- ESTA LÍNEA ES LA CLAVE
  const text = input.value.trim();
  if (text) {
    send(text);
    input.value = "";
  }
});

// Mensaje de bienvenida
addBubble("ai", "¿Qué necesitas hoy? Puedo buscar en Wikipedia, decirte la hora por país o charlar.");
