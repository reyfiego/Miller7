const SESSION_KEY = "miller_session_id";
let sessionId = localStorage.getItem(SESSION_KEY) || null;

// Secciones
const chatSection = document.getElementById("chat-section");
const loginSection = document.getElementById("login-section");
const registerSection = document.getElementById("register-section");

// Chat
const chatEl = document.getElementById("chat");
const form = document.getElementById("composer-form");
const input = document.getElementById("prompt");
const micBtn = document.getElementById("mic-btn");
const overlay = document.getElementById("voice-overlay");
const confirmBtn = document.getElementById("confirm");
const cancelBtn = document.getElementById("cancel");
const waveBar = overlay.querySelector(".wave-level");

// Botones login/registro
const btnShowLogin = document.getElementById("btn-show-login");
const btnShowRegister = document.getElementById("btn-show-register");

// Modal info
const infoBtn = document.getElementById("info-btn");
const modal = document.getElementById("info-modal");
const closeModal = document.getElementById("close-modal");

infoBtn.addEventListener("click", () => modal.style.display="block");
closeModal.addEventListener("click", () => modal.style.display="none");
window.addEventListener("click", e => { if(e.target===modal) modal.style.display="none"; });

// -------------------- MOSTRAR SECCIONES --------------------
function showSection(section) {
  chatSection.style.display = "none";
  loginSection.style.display = "none";
  registerSection.style.display = "none";
  section.style.display = "flex";
}

// Inicial: si hay sesión, mostrar chat; sino, login
if(sessionId) showSection(chatSection);
else showSection(loginSection);

// Asociar botones
btnShowLogin.addEventListener("click", () => showSection(loginSection));
btnShowRegister.addEventListener("click", () => showSection(registerSection));

// -------------------- CHAT --------------------
function addBubble(sender, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender}`;
  bubble.innerHTML = `<strong>${sender==="you"?"Tú":"Miller"}:</strong> ${escapeHtml(text)}`;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
}
function escapeHtml(str) {
  return str.replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[s]));
}
async function send(text) {
  addBubble("you", text);
  input.value = "";
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
  } catch(err) { addBubble("ai", "❌ Error al conectar con el servidor."); console.error(err); }
}
form.addEventListener("submit", e => { e.preventDefault(); if(input.value.trim()) send(input.value.trim()); });

// -------------------- MICRÓFONO --------------------
let recognition;
let currentTranscript = "";
if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = "es-ES"; recognition.interimResults = true;
  recognition.addEventListener("result", e => {
    currentTranscript = Array.from(e.results).map(r=>r[0].transcript).join(" ");
    waveBar.style.width = Math.min(100, Math.random()*100)+"%";
  });
  recognition.addEventListener("end", ()=>{ micBtn.disabled=false; waveBar.style.width="0%"; });
  micBtn.addEventListener("click", ()=>{ overlay.style.display="flex"; micBtn.disabled=true; recognition.start(); });
  confirmBtn.addEventListener("click", ()=>{ if(currentTranscript.trim()) send(currentTranscript); overlay.style.display="none"; currentTranscript=""; waveBar.style.width="0%"; });
  cancelBtn.addEventListener("click", ()=>{ overlay.style.display="none"; currentTranscript=""; waveBar.style.width="0%"; });
} else { micBtn.disabled=true; micBtn.title="Tu navegador no soporta reconocimiento de voz"; }

// -------------------- LOGIN & REGISTRO --------------------
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginUserInput = document.getElementById("login-username");
const loginPassInput = document.getElementById("login-password");
const regEmailInput = document.getElementById("register-email");
const regUserInput = document.getElementById("register-username");
const regPassInput = document.getElementById("register-password");
const rememberLogin = document.getElementById("remember-login");
const rememberRegister = document.getElementById("remember-register");

async function handleRegister(e){
  e.preventDefault();
  if(!grecaptcha.getResponse()) { alert("Completa el CAPTCHA"); return; }
  const payload = { email: regEmailInput.value.trim(), username: regUserInput.value.trim(), password: regPassInput.value.trim() };
  try{
    const res = await fetch("/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const data = await res.json();
    alert(data.message||"Registro completado.");
    if(data.success){ registerForm.reset(); showSection(loginSection); if(rememberRegister.checked){ localStorage.setItem(SESSION_KEY, data.session_id); sessionId=data.session_id; } }
  } catch(err){ console.error(err); alert("Error al registrarse."); }
}

async function handleLogin(e){
  e.preventDefault();
  if(!grecaptcha.getResponse()) { alert("Completa el CAPTCHA"); return; }
  const payload = { username: loginUserInput.value.trim(), password: loginPassInput.value.trim() };
  try{
    const res = await fetch("/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const data = await res.json();
    if(data.success){ if(rememberLogin.checked){ localStorage.setItem(SESSION_KEY,data.session_id); } sessionId=data.session_id; alert("Login exitoso"); loginForm.reset(); showSection(chatSection); } 
    else alert(data.message||"Usuario o contraseña incorrectos.");
  }catch(err){ console.error(err); alert("Error al loguearse."); }
}

if(registerForm) registerForm.addEventListener("submit", handleRegister);
if(loginForm) loginForm.addEventListener("submit", handleLogin);

// Bienvenida
async function showGreeting() {
  try{
    const res = await fetch("/greeting"); const data = await res.json();
    if(data.greeting) addBubble("ai", data.greeting);
  } catch(err){ addBubble("ai", "¡Hola! Estoy listo para charlar contigo."); }
}
showGreeting();
