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

    const removeButton = document.createElement("button");
    removeButton.textContent = "Remove";
    removeButton.className = "link-action danger";
    removeButton.addEventListener("click", () => removeDocument(doc));

    actionsCell.append(downloadLink, removeButton);

    row.append(nameCell, folderCell, typeCell, sizeCell, checksumCell, uploadedCell, actionsCell);
    documentsTbodyEl.appendChild(row);
  });
}

async function loadDocuments() {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/documents`);
  if (!res.ok) return;
  const docs = await res.json();
  renderDocuments(docs);
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

loadProject().then(() => {
  if (projectId) loadDocuments();
});
