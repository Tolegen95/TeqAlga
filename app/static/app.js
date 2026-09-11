const form = document.querySelector("#meeting-form");
const fileInput = document.querySelector("#audio-file");
const fileLabel = document.querySelector("#file-label");
const dropzone = document.querySelector("#dropzone");
const submitButton = document.querySelector("#submit-button");
const progressCard = document.querySelector("#progress-card");
const progressStage = document.querySelector("#progress-stage");
const progressValue = document.querySelector("#progress-value");
const progressBar = document.querySelector("#progress-bar");
const errorCard = document.querySelector("#error-card");
const results = document.querySelector("#results");

let currentMeetingId = null;
let transcriptById = new Map();
let timestampsPrecise = true;

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const formatTime = (seconds) => {
  const total = Math.max(0, Math.floor(seconds || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  return [hours, minutes, secs].map((value) => String(value).padStart(2, "0")).join(":");
};

async function checkRuntime() {
  const statusDot = document.querySelector("#status-dot");
  const statusText = document.querySelector("#runtime-status");
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    const allReady = health.ffmpeg && health.ollama && health.diarization_model;
    statusDot.classList.add(allReady ? "ready" : "partial");
    statusText.textContent = allReady
      ? `Готово · ${health.ollama_model} · Offline`
      : "Приложение запущено · проверьте модели";
  } catch {
    statusText.textContent = "Локальный сервис недоступен";
  }
}

function setSelectedFile(file) {
  if (!file) return;
  fileLabel.textContent = file.name;
  dropzone.classList.add("selected");
}

fileInput.addEventListener("change", () => setSelectedFile(fileInput.files[0]));
["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
  });
});
dropzone.addEventListener("drop", (event) => {
  const files = event.dataTransfer.files;
  if (!files.length) return;
  const transfer = new DataTransfer();
  transfer.items.add(files[0]);
  fileInput.files = transfer.files;
  setSelectedFile(files[0]);
});

function updateProgress(progress, stage) {
  progressCard.classList.remove("hidden");
  progressValue.textContent = `${progress}%`;
  progressStage.textContent = stage;
  progressBar.style.width = `${progress}%`;
}

function showError(message) {
  errorCard.textContent = message;
  errorCard.classList.remove("hidden");
  submitButton.disabled = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorCard.classList.add("hidden");
  results.classList.add("hidden");
  submitButton.disabled = true;
  updateProgress(1, "Загрузка локального файла");

  const payload = new FormData(form);
  if (!document.querySelector("#num-speakers").value) payload.delete("num_speakers");

  try {
    const response = await fetch("/api/v1/meetings", { method: "POST", body: payload });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Не удалось запустить обработку");
    }
    const job = await response.json();
    pollJob(job.id);
  } catch (error) {
    showError(error.message);
  }
});

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/v1/jobs/${jobId}`);
    if (!response.ok) throw new Error("Не удалось получить статус обработки");
    const job = await response.json();
    updateProgress(job.progress, job.stage);
    if (job.status === "completed") {
      currentMeetingId = job.meeting_id;
      await loadMeeting(job.meeting_id);
      submitButton.disabled = false;
      return;
    }
    if (job.status === "failed") throw new Error(job.error || "Обработка завершилась ошибкой");
    window.setTimeout(() => pollJob(jobId), 1100);
  } catch (error) {
    showError(error.message);
  }
}

async function loadMeeting(meetingId) {
  const response = await fetch(`/api/v1/meetings/${meetingId}`);
  if (!response.ok) throw new Error("Протокол не найден");
  const meeting = await response.json();
  renderMeeting(meeting);
}

function evidenceHtml(ids) {
  return (ids || []).map((id) => {
    const segment = transcriptById.get(id);
    const label = segment && timestampsPrecise ? formatTime(segment.start) : id;
    return `<button type="button" data-evidence="${escapeHtml(id)}">${escapeHtml(label)}</button>`;
  }).join("");
}

function renderFindings(selector, items) {
  const target = document.querySelector(selector);
  if (!items?.length) {
    target.innerHTML = '<span class="empty-state">Не зафиксировано</span>';
    return;
  }
  target.innerHTML = items.map((item) => `
    <div class="finding">
      <div>
        ${escapeHtml(item.text)}
        <div class="evidence">${evidenceHtml(item.evidence)}</div>
      </div>
    </div>`).join("");
}

function renderMeeting(meeting) {
  timestampsPrecise = meeting.metadata.timestamps_precise;
  transcriptById = new Map(meeting.transcript.map((segment) => [segment.id, segment]));
  document.querySelector("#result-title").textContent = meeting.metadata.title;
  document.querySelector("#metadata").innerHTML = `
    <span>${escapeHtml(meeting.metadata.speaker_count)} спикеров</span>
    <span>${timestampsPrecise ? escapeHtml(formatTime(meeting.metadata.duration_seconds)) : "Готовый транскрипт"}</span>
    <span>${escapeHtml(meeting.metadata.language || "Язык не определён")}</span>
    <span>Отчёт: ${escapeHtml(meeting.metadata.report_language || "ru")}</span>
    <span>${escapeHtml(meeting.metadata.llm_model)}</span>`;

  renderFindings("#summary-list", meeting.report.executive_summary);
  renderFindings("#facts-list", meeting.report.key_facts);
  renderFindings("#decisions-list", meeting.report.decisions);
  renderFindings("#questions-list", meeting.report.open_questions);
  renderFindings("#risks-list", meeting.report.risks);

  const actionsTable = document.querySelector("#actions-table");
  actionsTable.innerHTML = meeting.report.action_items.length
    ? meeting.report.action_items.map((item) => `
      <tr>
        <td>${escapeHtml(item.owner || "Не указан")}</td>
        <td>${escapeHtml(item.task)}</td>
        <td>${escapeHtml(item.due_date || "Не указан")}</td>
        <td><span class="priority ${escapeHtml(item.priority)}">${escapeHtml(item.priority)}</span></td>
        <td><div class="evidence">${evidenceHtml(item.evidence)}</div></td>
      </tr>`).join("")
    : '<tr><td colspan="5" class="empty-state">Поручения не зафиксированы</td></tr>';

  document.querySelector("#transcript-list").innerHTML = meeting.transcript.map((segment) => `
    <article class="segment" id="${escapeHtml(segment.id)}">
      <span class="segment-time">${timestampsPrecise ? escapeHtml(formatTime(segment.start)) : escapeHtml(segment.id)}</span>
      <strong class="segment-speaker">${escapeHtml(segment.speaker)}</strong>
      <span class="segment-text">${escapeHtml(segment.text)}</span>
    </article>`).join("");

  progressCard.classList.add("hidden");
  document.querySelector("#empty-preview").classList.add("hidden");
  results.classList.remove("hidden");
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

document.addEventListener("click", (event) => {
  const evidenceButton = event.target.closest("[data-evidence]");
  if (evidenceButton) {
    activateTab("transcript");
    const segment = document.getElementById(evidenceButton.dataset.evidence);
    if (segment) {
      document.querySelectorAll(".segment.highlight").forEach((item) => item.classList.remove("highlight"));
      segment.classList.add("highlight");
      segment.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  const tabButton = event.target.closest("[data-tab]");
  if (tabButton) activateTab(tabButton.dataset.tab);

  const exportButton = event.target.closest("[data-export]");
  if (exportButton && currentMeetingId) {
    window.location.href = `/api/v1/meetings/${currentMeetingId}/export/${exportButton.dataset.export}`;
  }
});

function activateTab(name) {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".tab-page").forEach((page) => page.classList.remove("active"));
  document.querySelector(`#tab-${name}`).classList.add("active");
}

checkRuntime();
