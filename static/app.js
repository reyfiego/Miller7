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

