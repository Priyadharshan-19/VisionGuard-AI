// frontend/app.js
const BASE_URL = "http://127.0.0.1:5000";  // Your Flask backend URL
const STATUS_URL = `${BASE_URL}/status`;
const ASK_URL = `${BASE_URL}/ask`;

const leftMeta = document.getElementById("left_meta");
const rightMeta = document.getElementById("right_meta");
const leftImgLink = document.getElementById("left_img_link");
const rightImgLink = document.getElementById("right_img_link");

const llmBadge = document.getElementById("llm_badge");
const askBtn = document.getElementById("ask_btn");
const copyBtn = document.getElementById("copy_status");
const questionInput = document.getElementById("user_question");
const spinner = document.getElementById("spinner");

const respSummary = document.getElementById("resp_summary");
const respRisk = document.getElementById("resp_risk");
const respSuggestion = document.getElementById("resp_suggestion");
const historyLog = document.getElementById("history_log");

let lastStatus = null;

// ---------- POLLING STATUS ----------
async function fetchStatus() {
  try {
    const res = await fetch(STATUS_URL);
    if (!res.ok) throw new Error("Status fetch failed");
    const json = await res.json();
    lastStatus = json;

    leftMeta.innerHTML = `
      Label: <strong>${json.label || "—"}</strong> &nbsp;
      Confidence: <strong>${(json.confidence || 0).toFixed(2)}</strong>
    `;
    rightMeta.innerHTML = `
      Adv Score: <strong>${(json.adv_score || 0).toFixed(2)}</strong> &nbsp;
      Flag: <strong style="color:${json.adv_flag ? 'red' : 'limegreen'};">
        ${json.adv_flag ? "YES" : "NO"}
      </strong>
    `;

    leftImgLink.href = `/captured_frames/left_latest.jpg?ts=${Date.now()}`;
    rightImgLink.href = `/captured_frames/right_latest.jpg?ts=${Date.now()}`;
  } catch (e) {
    console.warn("Status fetch failed:", e);
  }
}

// ---------- LLM ASK FEATURE ----------
async function askLLM() {
  const q = questionInput.value.trim();
  if (!q) return alert("⚠️ Type a question first!");
  if (!lastStatus) return alert("Wait a moment — detection not ready yet.");

  llmBadge.className = "llm busy";
  llmBadge.innerText = "LLM: thinking...";
  spinner.hidden = false;
  askBtn.disabled = true;

  try {
    const payload = { question: q, context: lastStatus };
    const res = await fetch(ASK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Ask API failed");
    const data = await res.json();

    respSummary.innerText = data.summary || "—";
    respRisk.innerText = data.risk || "—";
    respSuggestion.innerText = data.suggestion || "—";

    const entry = document.createElement("div");
    entry.innerHTML = `<strong>Q:</strong> ${escapeHtml(q)}<br><strong>A:</strong> ${escapeHtml(data.summary || "-")}<hr/>`;
    historyLog.prepend(entry);

  } catch (err) {
    alert("❌ LLM request failed: " + err.message);
  } finally {
    llmBadge.className = "llm idle";
    llmBadge.innerText = "LLM: idle";
    spinner.hidden = true;
    askBtn.disabled = false;
  }
}

copyBtn.addEventListener("click", () => {
  if (!lastStatus) return alert("No status yet!");
  navigator.clipboard.writeText(JSON.stringify(lastStatus, null, 2))
    .then(() => alert("✅ Status copied!"));
});

askBtn.addEventListener("click", askLLM);
window.addEventListener("load", fetchStatus);
setInterval(fetchStatus, 1000);

function escapeHtml(s) {
  return s?.replace(/[&<>'"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"' : "&quot;" }[c])) || "";
}
