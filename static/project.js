// Project detail page: loads a single project, handles document upload and inventory.

const detailEl = document.getElementById("project-detail");
const uploadCardEl = document.getElementById("upload-card");
const documentsCardEl = document.getElementById("documents-card");
const uploadStatusEl = document.getElementById("upload-status");
const fileInputEl = document.getElementById("file-input");
const folderInputEl = document.getElementById("folder-input");
const folderInputLabelEl = document.getElementById("folder-input-label");
const documentsTbodyEl = document.getElementById("documents-tbody");
const documentsEmptyEl = document.getElementById("documents-empty");
const breadcrumbEl = document.getElementById("app-breadcrumb");
const inspectDialogEl = document.getElementById("inspect-dialog");
const inspectFormEl = document.getElementById("inspect-form");
const inspectDialogTextEl = document.getElementById("inspect-dialog-text");
const inspectErrorEl = document.getElementById("inspect-error");
const cancelInspectButtonEl = document.getElementById("cancel-inspect");
const confirmInspectButtonEl = document.getElementById("confirm-inspect");
const crossAnalysisCardEl = document.getElementById("cross-analysis-card");
const crossAnalysisUnavailableHintEl = document.getElementById("cross-analysis-unavailable-hint");
const crossAnalysisOpenButtonEl = document.getElementById("cross-analysis-open-button");
const crossSelectDialogEl = document.getElementById("cross-select-dialog");
const crossSelectFormEl = document.getElementById("cross-select-form");
const crossSelectListEl = document.getElementById("cross-select-list");
const crossSelectTotalEl = document.getElementById("cross-select-total");
const crossSelectErrorEl = document.getElementById("cross-select-error");
const cancelCrossSelectButtonEl = document.getElementById("cancel-cross-select");
const continueCrossSelectButtonEl = document.getElementById("continue-cross-select");
const crossConfirmDialogEl = document.getElementById("cross-confirm-dialog");
const crossConfirmFormEl = document.getElementById("cross-confirm-form");
const crossConfirmListEl = document.getElementById("cross-confirm-list");
const crossConfirmErrorEl = document.getElementById("cross-confirm-error");
const backCrossConfirmButtonEl = document.getElementById("back-cross-confirm");
const sendCrossConfirmButtonEl = document.getElementById("send-cross-confirm");
const xlsxInspectDialogEl = document.getElementById("xlsx-inspect-dialog");
const xlsxInspectFormEl = document.getElementById("xlsx-inspect-form");
const xlsxInspectDialogTextEl = document.getElementById("xlsx-inspect-dialog-text");
const xlsxInspectErrorEl = document.getElementById("xlsx-inspect-error");
const cancelXlsxInspectButtonEl = document.getElementById("cancel-xlsx-inspect");
const confirmXlsxInspectButtonEl = document.getElementById("confirm-xlsx-inspect");
const validationLabCardEl = document.getElementById("validation-lab-card");
const validationLabLinkEl = document.getElementById("validation-lab-link");
const reconcileCardEl = document.getElementById("reconcile-card");
const reconcileUnavailableHintEl = document.getElementById("reconcile-unavailable-hint");
const reconcileOpenButtonEl = document.getElementById("reconcile-open-button");
const reconcileSelectDialogEl = document.getElementById("reconcile-select-dialog");
const reconcileSelectFormEl = document.getElementById("reconcile-select-form");
const reconcileSelectListEl = document.getElementById("reconcile-select-list");
const reconcileSelectTotalEl = document.getElementById("reconcile-select-total");
const reconcileSelectErrorEl = document.getElementById("reconcile-select-error");
const cancelReconcileSelectButtonEl = document.getElementById("cancel-reconcile-select");
const continueReconcileSelectButtonEl = document.getElementById("continue-reconcile-select");
const reconcileConfirmDialogEl = document.getElementById("reconcile-confirm-dialog");
const reconcileConfirmFormEl = document.getElementById("reconcile-confirm-form");
const reconcileConfirmListEl = document.getElementById("reconcile-confirm-list");
const reconcileConfirmErrorEl = document.getElementById("reconcile-confirm-error");
const backReconcileConfirmButtonEl = document.getElementById("back-reconcile-confirm");
const sendReconcileConfirmButtonEl = document.getElementById("send-reconcile-confirm");

// Must match cross_document_analysis.MAX_TOTAL_SOURCE_BYTES on the server -
// this is only used here to give the user an early, friendly heads-up;
// the server enforces the real limit regardless.
const CROSS_ANALYSIS_MAX_TOTAL_BYTES = 23 * 1024 * 1024;

const params = new URLSearchParams(window.location.search);
const projectId = params.get("id");

function formatDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

function setBreadcrumb(currentLabel) {
  breadcrumbEl.textContent = "";
  const homeLink = document.createElement("a");
  homeLink.href = "/";
  homeLink.textContent = "Home";
  const sep = document.createElement("span");
  sep.className = "sep";
  sep.textContent = "/";
  const current = document.createElement("span");
  current.className = "current";
  current.textContent = currentLabel;
  breadcrumbEl.append(homeLink, sep, current);
}

function renderNotFound() {
  detailEl.textContent = "";
  const p = document.createElement("p");
  p.textContent = "Project not found.";
  detailEl.appendChild(p);
  setBreadcrumb("Not found");
}

function renderProject(project) {
  detailEl.textContent = "";
  setBreadcrumb(project.name);

  const nameEl = document.createElement("div");
  nameEl.className = "name";
  nameEl.textContent = project.name;

  const metaEl = document.createElement("div");
  metaEl.className = "meta";
  metaEl.textContent = `Created ${formatDate(project.created_at)}`;

  const descLabel = document.createElement("div");
  descLabel.className = "section-label";
  descLabel.textContent = "Description";

  const descEl = document.createElement("div");
  descEl.className = "description";
  descEl.textContent = project.description || "No description provided.";

  const note = document.createElement("div");
  note.className = "placeholder-note";
  note.textContent = "AI-assisted analysis is not part of this build yet — this page will grow to support that.";

  detailEl.append(nameEl, metaEl, descLabel, descEl, note);
}

async function loadProject() {
  if (!projectId) {
    renderNotFound();
    return;
  }

  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`);
  if (!res.ok) {
    renderNotFound();
    return;
  }

  const project = await res.json();
  renderProject(project);
  uploadCardEl.hidden = false;
  documentsCardEl.hidden = false;
  renderDocumentsSkeleton();
}

function renderDocumentsSkeleton(rows = 3) {
  documentsTbodyEl.textContent = "";
  documentsEmptyEl.hidden = true;

  for (let i = 0; i < rows; i++) {
    const row = document.createElement("tr");
    row.className = "skeleton-row";
    for (let c = 0; c < 7; c++) {
      const cell = document.createElement("td");
      const line = document.createElement("div");
      line.className = "skeleton-line";
      cell.appendChild(line);
      row.appendChild(cell);
    }
    documentsTbodyEl.appendChild(row);
  }
}

function renderDocuments(docs) {
  documentsTbodyEl.textContent = "";
  documentsEmptyEl.hidden = docs.length !== 0;

  docs.forEach((doc, index) => {
    const row = document.createElement("tr");
    row.style.setProperty("--stagger-i", Math.min(index, 10));

    const nameCell = document.createElement("td");
    nameCell.textContent = doc.original_filename;

    const folderCell = document.createElement("td");
    folderCell.textContent = doc.relative_path || "—";
    folderCell.className = "muted";

    const typeCell = document.createElement("td");
    typeCell.textContent = doc.extension.replace(".", "").toUpperCase();

    const sizeCell = document.createElement("td");
    sizeCell.textContent = formatSize(doc.size_bytes);

    const checksumCell = document.createElement("td");
    checksumCell.className = "checksum";
    checksumCell.textContent = doc.sha256.slice(0, 12) + "…";
    checksumCell.title = doc.sha256;

    const uploadedCell = document.createElement("td");
    uploadedCell.textContent = formatDate(doc.uploaded_at);
    uploadedCell.className = "muted";

    const actionsCell = document.createElement("td");
    actionsCell.className = "actions";

    const downloadLink = document.createElement("a");
    downloadLink.href = `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(doc.id)}/download`;
    downloadLink.textContent = "Download";
    downloadLink.className = "link-action";

    actionsCell.append(downloadLink);

    if (doc.extension === ".pdf") {
      const inspectButton = document.createElement("button");
      inspectButton.textContent = "Inspect with Claude";
      inspectButton.className = "link-action";
      inspectButton.addEventListener("click", () => openInspectDialog(doc));
      actionsCell.append(inspectButton);
    }

    if (doc.extension === ".xlsx" || doc.extension === ".xls") {
      const inspectButton = document.createElement("button");
      inspectButton.textContent = "Inspect with Claude";
      inspectButton.className = "link-action";
      inspectButton.addEventListener("click", () => openXlsxInspectDialog(doc));
      actionsCell.append(inspectButton);
    }

    const removeButton = document.createElement("button");
    removeButton.textContent = "Remove";
    removeButton.className = "link-action danger";
    removeButton.addEventListener("click", () => removeDocument(doc));

    actionsCell.append(removeButton);

    row.append(nameCell, folderCell, typeCell, sizeCell, checksumCell, uploadedCell, actionsCell);
    documentsTbodyEl.appendChild(row);
  });
}

let latestDocuments = [];

async function loadDocuments() {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/documents`);
  if (!res.ok) return;
  const docs = await res.json();
  latestDocuments = docs;
  renderDocuments(docs);
  updateCrossAnalysisAvailability();

  validationLabCardEl.hidden = false;
  validationLabLinkEl.href = `/validation.html?project=${encodeURIComponent(projectId)}`;
}

function updateCrossAnalysisAvailability() {
  const pdfCount = latestDocuments.filter((d) => d.extension === ".pdf").length;
  crossAnalysisCardEl.hidden = false;
  const available = pdfCount >= 2;
  crossAnalysisOpenButtonEl.hidden = !available;
  crossAnalysisUnavailableHintEl.hidden = available;

  const excelCount = latestDocuments.filter((d) => d.extension === ".xlsx" || d.extension === ".xls").length;
  reconcileCardEl.hidden = false;
  const reconcileAvailable = pdfCount >= 1 && excelCount >= 1;
  reconcileOpenButtonEl.hidden = !reconcileAvailable;
  reconcileUnavailableHintEl.hidden = reconcileAvailable;
}

async function removeDocument(doc) {
  const confirmed = window.confirm(`Remove "${doc.original_filename}"? This cannot be undone.`);
  if (!confirmed) return;

  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(doc.id)}`,
    {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    }
  );

  if (res.ok) {
    await loadDocuments();
  } else {
    window.alert("Could not remove the document.");
  }
}

function statusLabel(status) {
  switch (status) {
    case "success":
      return "uploaded";
    case "duplicate":
      return "already uploaded (skipped)";
    case "unsupported_type":
      return "unsupported file type";
    default:
      return "failed";
  }
}

function renderUploadResults(results) {
  uploadStatusEl.textContent = "";
  if (results.length === 0) return;

  const list = document.createElement("ul");
  list.className = "upload-results";

  for (const result of results) {
    const item = document.createElement("li");
    item.className = `upload-result status-${result.status}`;
    const label = result.relative_path ? `${result.relative_path}/${result.filename}` : result.filename;
    item.textContent = `${label} — ${statusLabel(result.status)}`;
    list.appendChild(item);
  }

  uploadStatusEl.appendChild(list);
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList);
  if (files.length === 0) return;

  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name);
    formData.append("relative_paths", file.webkitRelativePath || "");
  }

  uploadStatusEl.textContent = "Uploading…";

  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/documents`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    uploadStatusEl.textContent = body.error || "Upload failed.";
    return;
  }

  const payload = await res.json();
  renderUploadResults(payload.results);
  await loadDocuments();
}

fileInputEl.addEventListener("change", () => {
  uploadFiles(fileInputEl.files);
  fileInputEl.value = "";
});

if ("webkitdirectory" in document.createElement("input")) {
  folderInputLabelEl.hidden = false;
  folderInputEl.addEventListener("change", () => {
    uploadFiles(folderInputEl.files);
    folderInputEl.value = "";
  });
}

// Drag-and-drop upload
const dropzoneEl = document.getElementById("upload-dropzone");

["dragenter", "dragover"].forEach((eventName) => {
  dropzoneEl.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzoneEl.classList.add("dragover");
  });
});

["dragleave", "dragend", "drop"].forEach((eventName) => {
  dropzoneEl.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzoneEl.classList.remove("dragover");
  });
});

dropzoneEl.addEventListener("drop", (event) => {
  const files = event.dataTransfer && event.dataTransfer.files;
  if (files && files.length) {
    uploadFiles(files);
  }
});

// Prevent the browser from navigating away if a file is dropped outside the zone.
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());

// PDF inspection

let pendingInspectDoc = null;

function openInspectDialog(doc) {
  pendingInspectDoc = doc;
  inspectDialogTextEl.textContent =
    `Send "${doc.original_filename}" to Anthropic's Claude API for analysis?`;
  inspectErrorEl.textContent = "";
  confirmInspectButtonEl.disabled = false;
  confirmInspectButtonEl.textContent = "Send to Claude";
  inspectDialogEl.showModal();
}

cancelInspectButtonEl.addEventListener("click", () => inspectDialogEl.close());

inspectDialogEl.addEventListener("click", (event) => {
  const rect = inspectDialogEl.getBoundingClientRect();
  const inDialog =
    rect.top <= event.clientY &&
    event.clientY <= rect.top + rect.height &&
    rect.left <= event.clientX &&
    event.clientX <= rect.left + rect.width;
  if (!inDialog) inspectDialogEl.close();
});

inspectFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!pendingInspectDoc) return;

  inspectErrorEl.textContent = "";
  confirmInspectButtonEl.disabled = true;
  cancelInspectButtonEl.disabled = true;
  confirmInspectButtonEl.textContent = "Analyzing… this can take a minute";

  try {
    const res = await fetch(
      `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(pendingInspectDoc.id)}/inspect`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      }
    );
    const record = await res.json().catch(() => null);

    if (!record || !record.id) {
      inspectErrorEl.textContent = (record && record.error) || "The inspection request failed.";
      return;
    }

    window.location.href = `/inspect.html?project=${encodeURIComponent(projectId)}&inspection=${encodeURIComponent(record.id)}`;
  } catch (err) {
    inspectErrorEl.textContent = "Could not reach the local app server.";
  } finally {
    confirmInspectButtonEl.disabled = false;
    cancelInspectButtonEl.disabled = false;
    confirmInspectButtonEl.textContent = "Send to Claude";
  }
});

// Cross-document analysis

function closeOnBackdropClick(dialogEl) {
  dialogEl.addEventListener("click", (event) => {
    const rect = dialogEl.getBoundingClientRect();
    const inDialog =
      rect.top <= event.clientY &&
      event.clientY <= rect.top + rect.height &&
      rect.left <= event.clientX &&
      event.clientX <= rect.left + rect.width;
    if (!inDialog) dialogEl.close();
  });
}

closeOnBackdropClick(crossSelectDialogEl);
closeOnBackdropClick(crossConfirmDialogEl);

function selectedCrossDocuments() {
  const checked = crossSelectListEl.querySelectorAll("input[type=checkbox]:checked");
  return Array.from(checked).map((input) => latestDocuments.find((d) => d.id === input.value));
}

function updateCrossSelectTotal() {
  const selected = selectedCrossDocuments();
  const totalBytes = selected.reduce((sum, d) => sum + d.size_bytes, 0);
  const overBudget = totalBytes > CROSS_ANALYSIS_MAX_TOTAL_BYTES;

  crossSelectTotalEl.textContent =
    `Selected: ${selected.length} file${selected.length === 1 ? "" : "s"}, ` +
    `${formatSize(totalBytes)} of a ${formatSize(CROSS_ANALYSIS_MAX_TOTAL_BYTES)} combined limit ` +
    `(Anthropic's own request limit is 32 MB, ~600 pages total).`;
  crossSelectTotalEl.classList.toggle("over-budget", overBudget);

  continueCrossSelectButtonEl.disabled = selected.length < 2 || overBudget;
}

function openCrossSelectDialog() {
  crossSelectListEl.textContent = "";
  crossSelectErrorEl.textContent = "";

  latestDocuments
    .filter((d) => d.extension === ".pdf")
    .forEach((doc) => {
      const item = document.createElement("li");
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = doc.id;
      checkbox.addEventListener("change", updateCrossSelectTotal);

      const text = document.createElement("span");
      text.textContent = `${doc.original_filename} — ${formatSize(doc.size_bytes)}`;

      label.append(checkbox, text);
      item.appendChild(label);
      crossSelectListEl.appendChild(item);
    });

  updateCrossSelectTotal();
  crossSelectDialogEl.showModal();
}

crossAnalysisOpenButtonEl.addEventListener("click", openCrossSelectDialog);
cancelCrossSelectButtonEl.addEventListener("click", () => crossSelectDialogEl.close());

let pendingCrossSelection = [];

crossSelectFormEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const selected = selectedCrossDocuments();
  if (selected.length < 2) {
    crossSelectErrorEl.textContent = "Select at least two PDFs.";
    return;
  }

  pendingCrossSelection = selected;
  crossSelectDialogEl.close();

  crossConfirmListEl.textContent = "";
  selected.forEach((doc) => {
    const item = document.createElement("li");
    item.textContent = doc.original_filename;
    crossConfirmListEl.appendChild(item);
  });
  crossConfirmErrorEl.textContent = "";
  sendCrossConfirmButtonEl.disabled = false;
  sendCrossConfirmButtonEl.textContent = "Send to Claude";
  crossConfirmDialogEl.showModal();
});

backCrossConfirmButtonEl.addEventListener("click", () => {
  crossConfirmDialogEl.close();
  crossSelectDialogEl.showModal();
});

crossConfirmFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (pendingCrossSelection.length < 2) return;

  crossConfirmErrorEl.textContent = "";
  sendCrossConfirmButtonEl.disabled = true;
  backCrossConfirmButtonEl.disabled = true;
  sendCrossConfirmButtonEl.textContent = "Analyzing… this can take a few minutes";

  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/cross-analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_ids: pendingCrossSelection.map((d) => d.id),
        confirm: true,
      }),
    });
    const record = await res.json().catch(() => null);

    if (!record || !record.id) {
      crossConfirmErrorEl.textContent = (record && record.error) || "The analysis request failed.";
      return;
    }

    window.location.href = `/cross-analysis.html?project=${encodeURIComponent(projectId)}&analysis=${encodeURIComponent(record.id)}`;
  } catch (err) {
    crossConfirmErrorEl.textContent = "Could not reach the local app server.";
  } finally {
    sendCrossConfirmButtonEl.disabled = false;
    backCrossConfirmButtonEl.disabled = false;
    sendCrossConfirmButtonEl.textContent = "Send to Claude";
  }
});

// Workbook (XLSX/XLS) inspection

let pendingXlsxInspectDoc = null;

function openXlsxInspectDialog(doc) {
  pendingXlsxInspectDoc = doc;
  xlsxInspectDialogTextEl.textContent =
    `Send "${doc.original_filename}" to Anthropic's Claude API for sandboxed workbook analysis?`;
  xlsxInspectErrorEl.textContent = "";
  confirmXlsxInspectButtonEl.disabled = false;
  confirmXlsxInspectButtonEl.textContent = "Send to Claude";
  xlsxInspectDialogEl.showModal();
}

cancelXlsxInspectButtonEl.addEventListener("click", () => xlsxInspectDialogEl.close());
closeOnBackdropClick(xlsxInspectDialogEl);

xlsxInspectFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!pendingXlsxInspectDoc) return;

  xlsxInspectErrorEl.textContent = "";
  confirmXlsxInspectButtonEl.disabled = true;
  cancelXlsxInspectButtonEl.disabled = true;
  confirmXlsxInspectButtonEl.textContent = "Analyzing… this can take several minutes";

  try {
    const res = await fetch(
      `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(pendingXlsxInspectDoc.id)}/inspect-workbook`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      }
    );
    const record = await res.json().catch(() => null);

    if (!record || !record.id) {
      xlsxInspectErrorEl.textContent = (record && record.error) || "The inspection request failed.";
      return;
    }

    window.location.href = `/workbook-inspect.html?project=${encodeURIComponent(projectId)}&inspection=${encodeURIComponent(record.id)}`;
  } catch (err) {
    xlsxInspectErrorEl.textContent = "Could not reach the local app server.";
  } finally {
    confirmXlsxInspectButtonEl.disabled = false;
    cancelXlsxInspectButtonEl.disabled = false;
    confirmXlsxInspectButtonEl.textContent = "Send to Claude";
  }
});

// Cross-format (PDF + Excel) deal reconciliation

function isExcelDoc(doc) {
  return doc.extension === ".xlsx" || doc.extension === ".xls";
}

function selectedReconcileDocuments() {
  const checked = reconcileSelectListEl.querySelectorAll("input[type=checkbox]:checked");
  return Array.from(checked).map((input) => latestDocuments.find((d) => d.id === input.value));
}

function updateReconcileSelectTotal() {
  const selected = selectedReconcileDocuments();
  const pdfs = selected.filter((d) => d.extension === ".pdf");
  const excels = selected.filter(isExcelDoc);
  const pdfBytes = pdfs.reduce((sum, d) => sum + d.size_bytes, 0);
  const overBudget = pdfBytes > CROSS_ANALYSIS_MAX_TOTAL_BYTES;

  reconcileSelectTotalEl.textContent =
    `Selected: ${pdfs.length} PDF${pdfs.length === 1 ? "" : "s"} (${formatSize(pdfBytes)} of a ` +
    `${formatSize(CROSS_ANALYSIS_MAX_TOTAL_BYTES)} combined limit), ${excels.length} Excel workbook` +
    `${excels.length === 1 ? "" : "s"} (each uploaded and capped individually).`;
  reconcileSelectTotalEl.classList.toggle("over-budget", overBudget);

  continueReconcileSelectButtonEl.disabled = pdfs.length < 1 || excels.length < 1 || overBudget;
}

function openReconcileSelectDialog() {
  reconcileSelectListEl.textContent = "";
  reconcileSelectErrorEl.textContent = "";

  latestDocuments
    .filter((d) => d.extension === ".pdf" || isExcelDoc(d))
    .forEach((doc) => {
      const item = document.createElement("li");
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = doc.id;
      checkbox.addEventListener("change", updateReconcileSelectTotal);

      const text = document.createElement("span");
      const typeLabel = doc.extension === ".pdf" ? "PDF" : doc.extension.replace(".", "").toUpperCase();
      text.textContent = `[${typeLabel}] ${doc.original_filename} — ${formatSize(doc.size_bytes)}`;

      label.append(checkbox, text);
      item.appendChild(label);
      reconcileSelectListEl.appendChild(item);
    });

  updateReconcileSelectTotal();
  reconcileSelectDialogEl.showModal();
}

reconcileOpenButtonEl.addEventListener("click", openReconcileSelectDialog);
cancelReconcileSelectButtonEl.addEventListener("click", () => reconcileSelectDialogEl.close());
closeOnBackdropClick(reconcileSelectDialogEl);
closeOnBackdropClick(reconcileConfirmDialogEl);

let pendingReconcileSelection = [];

reconcileSelectFormEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const selected = selectedReconcileDocuments();
  const pdfs = selected.filter((d) => d.extension === ".pdf");
  const excels = selected.filter(isExcelDoc);
  if (pdfs.length < 1 || excels.length < 1) {
    reconcileSelectErrorEl.textContent = "Select at least one PDF and at least one Excel workbook.";
    return;
  }

  pendingReconcileSelection = selected;
  reconcileSelectDialogEl.close();

  reconcileConfirmListEl.textContent = "";
  selected.forEach((doc) => {
    const item = document.createElement("li");
    const typeLabel = doc.extension === ".pdf" ? "PDF" : doc.extension.replace(".", "").toUpperCase();
    item.textContent = `[${typeLabel}] ${doc.original_filename}`;
    reconcileConfirmListEl.appendChild(item);
  });
  reconcileConfirmErrorEl.textContent = "";
  sendReconcileConfirmButtonEl.disabled = false;
  sendReconcileConfirmButtonEl.textContent = "Send to Claude";
  reconcileConfirmDialogEl.showModal();
});

backReconcileConfirmButtonEl.addEventListener("click", () => {
  reconcileConfirmDialogEl.close();
  reconcileSelectDialogEl.showModal();
});

reconcileConfirmFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (pendingReconcileSelection.length === 0) return;

  reconcileConfirmErrorEl.textContent = "";
  sendReconcileConfirmButtonEl.disabled = true;
  backReconcileConfirmButtonEl.disabled = true;
  sendReconcileConfirmButtonEl.textContent = "Analyzing… this can take several minutes";

  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/reconciliation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_ids: pendingReconcileSelection.map((d) => d.id),
        confirm: true,
      }),
    });
    const record = await res.json().catch(() => null);

    if (!record || !record.id) {
      reconcileConfirmErrorEl.textContent = (record && record.error) || "The reconciliation request failed.";
      return;
    }

    window.location.href = `/reconcile.html?project=${encodeURIComponent(projectId)}&analysis=${encodeURIComponent(record.id)}`;
  } catch (err) {
    reconcileConfirmErrorEl.textContent = "Could not reach the local app server.";
  } finally {
    sendReconcileConfirmButtonEl.disabled = false;
    backReconcileConfirmButtonEl.disabled = false;
    sendReconcileConfirmButtonEl.textContent = "Send to Claude";
  }
});

loadProject().then(() => {
  if (projectId) loadDocuments();
});
