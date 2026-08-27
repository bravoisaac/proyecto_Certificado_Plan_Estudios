const state = {
  pdf: null,
  rtf: null,
  equivalences: [],
};

const $ = (selector) => document.querySelector(selector);
const pdfInput = $("#pdf-input");
const rtfInput = $("#rtf-input");
const analyzeButton = $("#analyze-button");
const generateButton = $("#generate-button");
const message = $("#global-message");
const results = $("#results");
const list = $("#equivalence-list");
const selectAll = $("#select-all");

const limits = {
  pdf: 20 * 1024 * 1024,
  rtf: 25 * 1024 * 1024,
};

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function showMessage(text, type = "error") {
  message.textContent = text;
  message.className = `message ${type === "success" ? "success" : ""}`;
  message.hidden = false;
}

function clearMessage() {
  message.hidden = true;
  message.textContent = "";
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  button.classList.toggle("loading", busy);
  button.querySelector("span").textContent = label;
}

function validateFile(kind, file) {
  const expected = kind === "pdf" ? ".pdf" : ".rtf";
  if (!file.name.toLowerCase().endsWith(expected)) {
    throw new Error(`Selecciona un archivo ${expected.toUpperCase()} válido.`);
  }
  if (file.size > limits[kind]) {
    throw new Error(`El archivo supera el máximo de ${limits[kind] / (1024 * 1024)} MB.`);
  }
}

function setFile(kind, file) {
  if (!file) return;
  try {
    validateFile(kind, file);
    state[kind] = file;
    const zone = $(`#${kind}-zone`);
    zone.classList.add("ready");
    zone.querySelector(".dropzone-copy span").textContent = file.name;
    zone.querySelector(".dropzone-copy small").textContent = `${formatBytes(file.size)} · listo para procesar`;
    clearMessage();
  } catch (error) {
    state[kind] = null;
    showMessage(error.message);
  }
  const ready = Boolean(state.pdf && state.rtf);
  analyzeButton.disabled = !ready;
  $("#files-status").textContent = ready ? "Archivos listos" : "Esperando archivos";
  $("#files-status").classList.toggle("ready", ready);
}

function setupDropzone(kind, input) {
  const zone = $(`#${kind}-zone`);
  input.addEventListener("change", () => setFile(kind, input.files[0]));
  for (const event of ["dragenter", "dragover"]) {
    zone.addEventListener(event, (e) => {
      e.preventDefault();
      zone.classList.add("dragging");
    });
  }
  for (const event of ["dragleave", "drop"]) {
    zone.addEventListener(event, (e) => {
      e.preventDefault();
      zone.classList.remove("dragging");
    });
  }
  zone.addEventListener("drop", (e) => setFile(kind, e.dataTransfer.files[0]));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderEquivalences(payload) {
  state.equivalences = payload.equivalences.map((item, index) => ({ ...item, selected: item.found_in_rtf, id: index }));
  $("#equivalence-count").textContent = state.equivalences.length;
  const warnings = [...payload.warnings];
  if (!state.equivalences.length) warnings.push("No se encontraron equivalencias aprobadas en el PDF.");
  $("#warning-list").innerHTML = warnings.map((warning) => `<div class="warning-item">${escapeHtml(warning)}</div>`).join("");

  list.innerHTML = state.equivalences.map((item) => `
    <div class="equivalence-row ${item.found_in_rtf ? "" : "unmatched"}" data-id="${item.id}">
      <input class="row-select" type="checkbox" aria-label="Incluir equivalencia de ${escapeHtml(item.subject_code)}" ${item.selected ? "checked" : ""} ${item.found_in_rtf ? "" : "disabled"} />
      <div class="subject">
        <span class="subject-code">${escapeHtml(item.subject_code)}</span>
        <span>${escapeHtml(item.subject_name)}</span>
      </div>
      <div class="equivalent-fields ${item.has_unrecognized_characters ? "unknown" : ""}">
        <div class="field">
          <label for="code-${item.id}">Código equivalente</label>
          <input id="code-${item.id}" class="equivalent-code" maxlength="20" value="${escapeHtml(item.equivalent_code)}" />
        </div>
        <div class="field">
          <label for="name-${item.id}">Nombre equivalente</label>
          <input id="name-${item.id}" class="equivalent-name" maxlength="300" value="${escapeHtml(item.equivalent_name)}" />
        </div>
        ${item.found_in_rtf ? "" : '<div class="match-note">Esta asignatura no aparece como ficha editable en el RTF.</div>'}
      </div>
    </div>
  `).join("");

  list.querySelectorAll(".equivalence-row").forEach((row) => {
    const item = state.equivalences[Number(row.dataset.id)];
    row.querySelector(".row-select").addEventListener("change", (event) => {
      item.selected = event.target.checked;
      updateSelection();
    });
    row.querySelector(".equivalent-code").addEventListener("input", (event) => {
      item.equivalent_code = event.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, "");
      event.target.value = item.equivalent_code;
    });
    row.querySelector(".equivalent-name").addEventListener("input", (event) => {
      item.equivalent_name = event.target.value;
      row.querySelector(".equivalent-fields").classList.toggle("unknown", event.target.value.includes("�"));
    });
  });

  selectAll.checked = state.equivalences.some((item) => item.found_in_rtf);
  selectAll.indeterminate = false;
  updateSelection();
  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateSelection() {
  const available = state.equivalences.filter((item) => item.found_in_rtf);
  const selected = available.filter((item) => item.selected);
  $("#selected-count").textContent = `${selected.length} seleccionada${selected.length === 1 ? "" : "s"}`;
  generateButton.disabled = selected.length === 0;
  selectAll.checked = selected.length > 0 && selected.length === available.length;
  selectAll.indeterminate = selected.length > 0 && selected.length < available.length;
}

analyzeButton.addEventListener("click", async () => {
  clearMessage();
  const form = new FormData();
  form.append("pdf", state.pdf);
  form.append("rtf", state.rtf);
  setBusy(analyzeButton, true, "Analizando documentos");
  try {
    const response = await fetch("/api/analyze", { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "No fue posible analizar los archivos.");
    renderEquivalences(payload);
  } catch (error) {
    showMessage(error.message);
  } finally {
    setBusy(analyzeButton, false, "Analizar equivalencias");
    analyzeButton.disabled = !(state.pdf && state.rtf);
  }
});

selectAll.addEventListener("change", () => {
  state.equivalences.forEach((item) => {
    if (item.found_in_rtf) item.selected = selectAll.checked;
  });
  list.querySelectorAll(".row-select:not(:disabled)").forEach((checkbox) => { checkbox.checked = selectAll.checked; });
  updateSelection();
});

$("#back-button").addEventListener("click", () => {
  results.hidden = true;
  document.querySelector(".workspace-card").scrollIntoView({ behavior: "smooth", block: "start" });
});

generateButton.addEventListener("click", async () => {
  clearMessage();
  const selected = state.equivalences
    .filter((item) => item.selected && item.found_in_rtf)
    .map(({ subject_code, equivalent_code, equivalent_name }) => ({ subject_code, equivalent_code, equivalent_name: equivalent_name.trim() }));
  if (selected.some((item) => !item.equivalent_code || !item.equivalent_name)) {
    showMessage("Completa el código y el nombre de todas las equivalencias seleccionadas.");
    return;
  }
  const form = new FormData();
  form.append("rtf", state.rtf);
  form.append("equivalences", new Blob([JSON.stringify(selected)], { type: "application/json" }), "equivalences.json");
  setBusy(generateButton, true, "Generando Word");
  try {
    const response = await fetch("/api/generate", { method: "POST", body: form });
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.error || "No fue posible generar el archivo.");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || "plan_con_equivalencias.rtf";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showMessage(`Archivo ${filename} generado correctamente.`, "success");
  } catch (error) {
    showMessage(error.message);
  } finally {
    setBusy(generateButton, false, "Generar Word completado");
    updateSelection();
  }
});

setupDropzone("pdf", pdfInput);
setupDropzone("rtf", rtfInput);
