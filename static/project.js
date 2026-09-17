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
const versionsDialogEl = document.getElementById("versions-dialog");
const versionsDialogNameEl = document.getElementById("versions-dialog-name");
const versionsListEl = document.getElementById("versions-list");
const closeVersionsButtonEl = document.getElementById("close-versions");
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
const reconciliationsCardEl = document.getElementById("reconciliations-card");
const reconciliationsListEl = document.getElementById("reconciliations-list");
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

// Task 11.4: deal brief
const briefCardEl = document.getElementById("brief-card");
const briefFormEl = document.getElementById("brief-form");
const briefVersionLabelEl = document.getElementById("brief-version-label");
const briefSaveHintEl = document.getElementById("brief-save-hint");
const briefHistoryButtonEl = document.getElementById("brief-history-button");
const briefVersionsDialogEl = document.getElementById("brief-versions-dialog");
const briefVersionsListEl = document.getElementById("brief-versions-list");
const closeBriefVersionsButtonEl = document.getElementById("close-brief-versions");
const BRIEF_FIELDS = ["parties", "objective", "perspective", "scope", "periods", "uncertainties"];

// Task 11.4: workstreams
const workstreamsCardEl = document.getElementById("workstreams-card");
const workstreamsListEl = document.getElementById("workstreams-list");
const workstreamsEmptyEl = document.getElementById("workstreams-empty");
const workstreamFormEl = document.getElementById("workstream-form");
const workstreamNameInputEl = document.getElementById("workstream-name");
const workstreamDescriptionInputEl = document.getElementById("workstream-description");
const workstreamErrorEl = document.getElementById("workstream-error");
let devIdentities = [];

// Task 13.4: deal memberships ("Deal access")
const membershipsCardEl = document.getElementById("memberships-card");
const membershipsListEl = document.getElementById("memberships-list");
const membershipsEmptyEl = document.getElementById("memberships-empty");
const membershipFormEl = document.getElementById("membership-form");
const membershipUserSelectEl = document.getElementById("membership-user");
const membershipRoleSelectEl = document.getElementById("membership-role");
const membershipErrorEl = document.getElementById("membership-error");

// Task 13.1: tasks, comments, work-product submissions
const tasksCardEl = document.getElementById("tasks-card");
const tasksListEl = document.getElementById("tasks-list");
const tasksEmptyEl = document.getElementById("tasks-empty");
const taskFormEl = document.getElementById("task-form");
const taskTitleInputEl = document.getElementById("task-title");
const taskDescriptionInputEl = document.getElementById("task-description");
const taskWorkstreamSelectEl = document.getElementById("task-workstream");
const taskAssigneeSelectEl = document.getElementById("task-assignee");
const taskErrorEl = document.getElementById("task-error");
const TASK_STATUS_LABELS = {
  open: "Open", in_progress: "In progress", submitted: "Submitted",
  returned: "Returned for revision", approved: "Approved", cancelled: "Cancelled",
};
// loadTasks() re-fetches and re-renders the whole list after every action
// (a comment, a status change, a submission) - tracked here so an
// in-progress conversation on one task doesn't visually collapse after
// every single message, the way it would with no memory of what was open.
const expandedTaskIds = new Set();

// Must match pdf_inspection.MAX_PDF_SOURCE_BYTES on the server (the shared
// combined-PDF-bytes cap used by cross-document analysis, cross-format
// reconciliation, and the Validation Lab) - this is only used here to give
// the user an early, friendly heads-up; the server enforces the real limit
// regardless, and honors DEAL_LAB_MAX_PDF_SOURCE_BYTES if that's overridden.
const CROSS_ANALYSIS_MAX_TOTAL_BYTES = 23.5 * 1024 * 1024;

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
  briefCardEl.hidden = false;
  workstreamsCardEl.hidden = false;
  membershipsCardEl.hidden = false;
  tasksCardEl.hidden = false;
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

// -- documents filters and sorting (Direction B: same idiom workspace.js's
// findings table already established - filters object + sortState object,
// a pure visibleDocuments() computing the filtered/sorted list, wired to
// re-render on every change) -------------------------------------------

const documentFilters = { search: "", folder: "all", type: "all" };
const documentSortState = { key: "original_filename", dir: "asc" };

function populateDocumentFilterOptions() {
  const folderSelect = document.getElementById("doc-filter-folder");
  const folders = Array.from(new Set(latestDocuments.map((d) => d.relative_path).filter(Boolean))).sort();
  folderSelect.textContent = "";
  [["all", "All"], ...folders.map((f) => [f, f])].forEach(([value, label]) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    folderSelect.appendChild(opt);
  });
  folderSelect.value = documentFilters.folder;

  const typeSelect = document.getElementById("doc-filter-type");
  const types = Array.from(new Set(latestDocuments.map((d) => d.extension))).sort();
  typeSelect.textContent = "";
  [["all", "All"], ...types.map((t) => [t, t.replace(".", "").toUpperCase()])].forEach(([value, label]) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    typeSelect.appendChild(opt);
  });
  typeSelect.value = documentFilters.type;

  document.getElementById("doc-filter-search").value = documentFilters.search;
}

function visibleDocuments() {
  const search = documentFilters.search.trim().toLowerCase();
  let list = latestDocuments.filter((d) => {
    if (documentFilters.folder !== "all" && d.relative_path !== documentFilters.folder) return false;
    if (documentFilters.type !== "all" && d.extension !== documentFilters.type) return false;
    if (search && !d.original_filename.toLowerCase().includes(search)) return false;
    return true;
  });

  const { key, dir } = documentSortState;
  list = list.slice().sort((a, b) => {
    let av, bv;
    if (key === "size_bytes") {
      av = a.size_bytes;
      bv = b.size_bytes;
    } else {
      av = (a[key] || "").toString().toLowerCase();
      bv = (b[key] || "").toString().toLowerCase();
    }
    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });
  return list;
}

function renderVisibleDocuments() {
  const docs = visibleDocuments();
  const total = latestDocuments.length;
  renderDocuments(docs);

  const filtersEl = document.getElementById("document-filters");
  const hint = document.getElementById("documents-count-hint");
  filtersEl.hidden = total === 0;
  hint.hidden = total === 0;
  hint.textContent =
    docs.length === total
      ? `${total} document${total === 1 ? "" : "s"}`
      : `${docs.length} of ${total} document${total === 1 ? "" : "s"}`;

  // renderDocuments() already toggled #documents-empty for "no rows to show"
  // - the two truly different reasons that can happen ("nothing uploaded
  // yet" vs "filters matched nothing") need different copy, or the filtered
  // case would wrongly tell someone with real documents to go upload some.
  document.getElementById("documents-empty-text").textContent =
    total === 0 ? "No documents uploaded yet." : "No documents match the current filters.";
}

document.querySelectorAll("#documents-table th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (documentSortState.key === key) {
      documentSortState.dir = documentSortState.dir === "asc" ? "desc" : "asc";
    } else {
      documentSortState.key = key;
      documentSortState.dir = "asc";
    }
    document.querySelectorAll("#documents-table th[data-sort]").forEach((h) => h.classList.remove("sorted", "sort-desc"));
    th.classList.add("sorted");
    if (documentSortState.dir === "desc") th.classList.add("sort-desc");
    renderVisibleDocuments();
  });
});

function wireDocumentFilterInput(id, key) {
  document.getElementById(id).addEventListener(id === "doc-filter-search" ? "input" : "change", (e) => {
    documentFilters[key] = e.target.value;
    renderVisibleDocuments();
  });
}
wireDocumentFilterInput("doc-filter-search", "search");
wireDocumentFilterInput("doc-filter-folder", "folder");
wireDocumentFilterInput("doc-filter-type", "type");

document.getElementById("doc-reset-filters").addEventListener("click", () => {
  documentFilters.search = "";
  documentFilters.folder = "all";
  documentFilters.type = "all";
  populateDocumentFilterOptions();
  renderVisibleDocuments();
});

function renderDocuments(docs) {
  documentsTbodyEl.textContent = "";
  documentsEmptyEl.hidden = docs.length !== 0;

  docs.forEach((doc, index) => {
    const row = document.createElement("tr");
    row.style.setProperty("--stagger-i", Math.min(index, 10));

    const nameCell = document.createElement("td");
    nameCell.textContent = doc.original_filename;
    if (doc.version_number > 1) {
      const versionBadge = document.createElement("span");
      versionBadge.className = "version-badge";
      versionBadge.textContent = `v${doc.version_number}`;
      versionBadge.title = `${doc.version_number} versions - current version shown here`;
      nameCell.append(versionBadge);
    }

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

    if (doc.version_number > 1) {
      const versionsButton = document.createElement("button");
      versionsButton.textContent = "Versions";
      versionsButton.className = "link-action";
      versionsButton.addEventListener("click", () => openVersionsDialog({
        name: doc.original_filename,
        currentVersionId: doc.current_version_id,
        listUrl: `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(doc.id)}/versions`,
        downloadUrlFor: (version) =>
          `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(doc.id)}/versions/${encodeURIComponent(version.id)}/download`,
      }));
      actionsCell.append(versionsButton);
    }

    const replaceLabel = document.createElement("label");
    replaceLabel.className = "link-action";
    replaceLabel.textContent = "Replace…";
    const replaceInput = document.createElement("input");
    replaceInput.type = "file";
    replaceInput.hidden = true;
    replaceInput.addEventListener("change", () => {
      if (replaceInput.files[0]) uploadNewVersion(doc, replaceInput.files[0]);
      replaceInput.value = "";
    });
    replaceLabel.append(replaceInput);
    actionsCell.append(replaceLabel);

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
  populateDocumentFilterOptions();
  renderVisibleDocuments();
  updateCrossAnalysisAvailability();

  validationLabCardEl.hidden = false;
  validationLabLinkEl.href = `/validation.html?project=${encodeURIComponent(projectId)}`;
}

async function loadReconciliations() {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/cross-format-analyses`);
  if (!res.ok) return;
  const records = await res.json();
  reconciliationsCardEl.hidden = records.length === 0;
  reconciliationsListEl.textContent = "";

  records.forEach((record, index) => {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.className = "project-item";
    link.href = `/reconcile.html?project=${encodeURIComponent(projectId)}&analysis=${encodeURIComponent(record.id)}`;
    link.style.setProperty("--stagger-i", Math.min(index, 10));

    const nameEl = document.createElement("div");
    nameEl.className = "name";
    nameEl.textContent = `Reconciliation — ${formatDate(record.created_at)}`;

    const descEl = document.createElement("div");
    descEl.className = "desc";
    const docCount = `${record.pdf_document_filenames.length} PDF, ${record.excel_document_filenames.length} Excel`;
    descEl.textContent = record.status === "success" ? `${docCount} · completed` : `${docCount} · did not complete`;

    link.append(nameEl, descEl);
    li.appendChild(link);
    reconciliationsListEl.appendChild(li);
  });
}

// -- Task 11.4: deal brief -------------------------------------------------

function fillBriefForm(version) {
  for (const field of BRIEF_FIELDS) {
    document.getElementById(`brief-${field}`).value = version ? version[field] : "";
  }
}

async function loadBrief() {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/brief`);
  if (!res.ok) return;
  const current = await res.json();
  fillBriefForm(current);
  if (current) {
    briefVersionLabelEl.textContent = `Version ${current.version_number} · saved ${formatDate(current.created_at)}`;
    briefHistoryButtonEl.hidden = current.version_number <= 1;
  } else {
    briefVersionLabelEl.textContent = "No version saved yet.";
    briefHistoryButtonEl.hidden = true;
  }
}

briefFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fields = {};
  for (const field of BRIEF_FIELDS) {
    fields[field] = document.getElementById(`brief-${field}`).value;
  }
  briefSaveHintEl.textContent = "Saving…";
  briefSaveHintEl.style.color = "";
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/brief`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    briefSaveHintEl.textContent = body.error || "Could not save the brief.";
    briefSaveHintEl.style.color = "var(--danger)";
    return;
  }
  briefSaveHintEl.textContent = "Saved as a new version.";
  briefSaveHintEl.style.color = "var(--success)";
  await loadBrief();
});

briefHistoryButtonEl.addEventListener("click", async () => {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/brief/versions`);
  const versions = res.ok ? await res.json() : [];
  briefVersionsListEl.textContent = "";
  versions
    .slice()
    .reverse()
    .forEach((version) => {
      const item = document.createElement("li");
      const meta = document.createElement("span");
      meta.className = "version-meta";
      meta.textContent = `Version ${version.version_number} · ${formatDate(version.created_at)}`;
      const viewButton = document.createElement("button");
      viewButton.type = "button";
      viewButton.className = "link-action";
      viewButton.textContent = "View";
      viewButton.addEventListener("click", () => {
        fillBriefForm(version);
        briefVersionsDialogEl.close();
        briefSaveHintEl.textContent = `Viewing version ${version.version_number} (not yet saved as current - edit and save to make it current).`;
        briefSaveHintEl.style.color = "";
      });
      item.append(meta, viewButton);
      briefVersionsListEl.appendChild(item);
    });
  briefVersionsDialogEl.showModal();
});

closeBriefVersionsButtonEl.addEventListener("click", () => briefVersionsDialogEl.close());

// -- Task 11.4: workstreams --------------------------------------------------

async function loadDevIdentities() {
  const res = await fetch("/api/dev/identities");
  devIdentities = res.ok ? await res.json() : [];
}

function renderWorkstream(workstream) {
  const li = document.createElement("li");
  li.className = "workstream-item";

  const header = document.createElement("div");
  header.className = "workstream-header";
  const nameEl = document.createElement("div");
  nameEl.className = "name";
  nameEl.textContent = workstream.name;
  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "link-action danger";
  removeButton.textContent = "Remove";
  removeButton.addEventListener("click", () => removeWorkstream(workstream));
  header.append(nameEl, removeButton);
  li.appendChild(header);

  if (workstream.description) {
    const descEl = document.createElement("div");
    descEl.className = "desc";
    descEl.textContent = workstream.description;
    li.appendChild(descEl);
  }

  const rosterEl = document.createElement("ul");
  rosterEl.className = "workstream-roster";
  workstream.assignments.forEach((assignment) => {
    const item = document.createElement("li");
    const label = document.createElement("span");
    const name = assignment.user ? assignment.user.display_name : "Unknown identity";
    label.textContent = assignment.role_label ? `${name} — ${assignment.role_label}` : name;
    const revokeButton = document.createElement("button");
    revokeButton.type = "button";
    revokeButton.className = "link-action danger";
    revokeButton.textContent = "Unassign";
    revokeButton.addEventListener("click", () => revokeAssignment(workstream, assignment));
    item.append(label, revokeButton);
    rosterEl.appendChild(item);
  });
  li.appendChild(rosterEl);

  const assignForm = document.createElement("form");
  assignForm.className = "workstream-assign-form";
  const select = document.createElement("select");
  select.setAttribute("aria-label", `Assign someone to ${workstream.name}`);
  devIdentities.forEach((identity) => {
    const option = document.createElement("option");
    option.value = identity.user.id;
    option.textContent = identity.user.display_name;
    select.appendChild(option);
  });
  const roleInput = document.createElement("input");
  roleInput.type = "text";
  roleInput.placeholder = "Role label (e.g. Lead)";
  roleInput.maxLength = 100;
  const assignButton = document.createElement("button");
  assignButton.type = "submit";
  assignButton.textContent = "Assign";
  assignForm.append(select, roleInput, assignButton);
  assignForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await assignToWorkstream(workstream, select.value, roleInput.value);
  });
  li.appendChild(assignForm);

  return li;
}

async function loadWorkstreams() {
  await loadDevIdentities();
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/workstreams`);
  if (!res.ok) return;
  const list = await res.json();
  workstreamsListEl.textContent = "";
  workstreamsEmptyEl.hidden = list.length !== 0;
  list.forEach((workstream) => workstreamsListEl.appendChild(renderWorkstream(workstream)));
}

async function assignToWorkstream(workstream, userId, roleLabel) {
  if (!userId) return;
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/workstreams/${encodeURIComponent(workstream.id)}/assignments`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, role_label: roleLabel }),
    }
  );
  if (res.ok) await loadWorkstreams();
}

async function revokeAssignment(workstream, assignment) {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/workstreams/${encodeURIComponent(workstream.id)}/assignments/${encodeURIComponent(assignment.user_id)}`,
    { method: "DELETE" }
  );
  if (res.ok) await loadWorkstreams();
}

async function removeWorkstream(workstream) {
  const confirmed = window.confirm(`Remove the "${workstream.name}" workstream? This cannot be undone.`);
  if (!confirmed) return;
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/workstreams/${encodeURIComponent(workstream.id)}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm: true }),
  });
  if (res.ok) await loadWorkstreams();
}

workstreamFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  workstreamErrorEl.textContent = "";
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/workstreams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: workstreamNameInputEl.value,
      description: workstreamDescriptionInputEl.value,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    workstreamErrorEl.textContent = body.error || "Could not create the workstream.";
    return;
  }
  workstreamNameInputEl.value = "";
  workstreamDescriptionInputEl.value = "";
  await loadWorkstreams();
});

// -- Task 13.4: deal memberships ("Deal access") ----------------------------

const MEMBERSHIP_ROLE_LABELS = {
  analyst: "Analyst",
  reviewer: "Reviewer",
  deal_lead: "Deal lead",
  external_executive: "External executive",
};

function renderMembership(membership) {
  const li = document.createElement("li");
  li.className = "workstream-item";

  const header = document.createElement("div");
  header.className = "workstream-header";
  const nameEl = document.createElement("div");
  nameEl.className = "name";
  const displayName = membership.user ? membership.user.display_name : "Unknown identity";
  const roleLabel = MEMBERSHIP_ROLE_LABELS[membership.role] || membership.role;
  nameEl.textContent = `${displayName} — ${roleLabel}`;
  header.appendChild(nameEl);

  if (membership.revoked_at) {
    const revokedEl = document.createElement("span");
    revokedEl.className = "desc";
    revokedEl.textContent = "Revoked";
    header.appendChild(revokedEl);
  } else {
    const revokeButton = document.createElement("button");
    revokeButton.type = "button";
    revokeButton.className = "link-action danger";
    revokeButton.textContent = "Revoke";
    revokeButton.addEventListener("click", () => revokeMembership(membership));
    header.appendChild(revokeButton);
  }
  li.appendChild(header);
  return li;
}

async function loadMemberships() {
  await loadDevIdentities();
  membershipUserSelectEl.textContent = "";
  devIdentities.forEach((identity) => {
    const option = document.createElement("option");
    option.value = identity.user.id;
    option.textContent = identity.user.display_name;
    membershipUserSelectEl.appendChild(option);
  });

  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/memberships`);
  if (!res.ok) return;
  const list = await res.json();
  const active = list.filter((m) => !m.revoked_at);
  membershipsListEl.textContent = "";
  membershipsEmptyEl.hidden = active.length !== 0;
  active.forEach((membership) => membershipsListEl.appendChild(renderMembership(membership)));
}

async function revokeMembership(membership) {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/memberships/${encodeURIComponent(membership.user_id)}`,
    { method: "DELETE" }
  );
  if (res.ok) await loadMemberships();
}

membershipFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  membershipErrorEl.textContent = "";
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/memberships`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: membershipUserSelectEl.value,
      role: membershipRoleSelectEl.value,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    membershipErrorEl.textContent = body.error || "Could not grant access.";
    return;
  }
  await loadMemberships();
});

// -- Task 13.1: tasks, comments, work-product submissions ------------------

async function populateTaskFormOptions() {
  await loadDevIdentities();
  const wsRes = await fetch(`/api/projects/${encodeURIComponent(projectId)}/workstreams`);
  const workstreamsForOptions = wsRes.ok ? await wsRes.json() : [];

  const fillIdentityOptions = (select, placeholderText) => {
    select.textContent = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = placeholderText;
    select.appendChild(placeholder);
    devIdentities.forEach((devIdentity) => {
      const option = document.createElement("option");
      option.value = devIdentity.user.id;
      option.textContent = devIdentity.user.display_name;
      select.appendChild(option);
    });
  };
  fillIdentityOptions(taskAssigneeSelectEl, "Unassigned");

  taskWorkstreamSelectEl.textContent = "";
  const noneOption = document.createElement("option");
  noneOption.value = "";
  noneOption.textContent = "None";
  taskWorkstreamSelectEl.appendChild(noneOption);
  workstreamsForOptions.forEach((workstream) => {
    const option = document.createElement("option");
    option.value = workstream.id;
    option.textContent = workstream.name;
    taskWorkstreamSelectEl.appendChild(option);
  });
}

function renderWorkProduct(task, workProduct) {
  const li = document.createElement("li");
  li.className = "task-work-product";

  const header = document.createElement("div");
  header.className = "task-work-product-header";
  const nameEl = document.createElement("span");
  nameEl.textContent = `${workProduct.title} (v${workProduct.version_number})`;
  header.appendChild(nameEl);

  const downloadLink = document.createElement("a");
  downloadLink.className = "link-action";
  downloadLink.textContent = "Download current";
  downloadLink.href = `/api/projects/${encodeURIComponent(projectId)}/work-products/${encodeURIComponent(workProduct.id)}/versions/${encodeURIComponent(workProduct.current_version_id)}/download`;
  header.appendChild(downloadLink);

  if (workProduct.versions.length > 1) {
    const versionsButton = document.createElement("button");
    versionsButton.type = "button";
    versionsButton.className = "link-action";
    versionsButton.textContent = "Versions";
    versionsButton.addEventListener("click", () => openVersionsDialog({
      name: workProduct.title,
      currentVersionId: workProduct.current_version_id,
      listUrl: `/api/projects/${encodeURIComponent(projectId)}/work-products/${encodeURIComponent(workProduct.id)}/versions`,
      downloadUrlFor: (version) =>
        `/api/projects/${encodeURIComponent(projectId)}/work-products/${encodeURIComponent(workProduct.id)}/versions/${encodeURIComponent(version.id)}/download`,
    }));
    header.appendChild(versionsButton);
  }
  if (workProduct.current_version_approved) {
    const approvedBadge = document.createElement("span");
    approvedBadge.className = "task-status task-status-approved";
    approvedBadge.textContent = "Current version approved";
    header.appendChild(approvedBadge);
  }
  li.appendChild(header);

  if (workProduct.review_decisions.length > 0) {
    const historyHeading = document.createElement("p");
    historyHeading.className = "task-review-history-heading";
    historyHeading.textContent = "Review history";
    li.appendChild(historyHeading);

    const historyList = document.createElement("ul");
    historyList.className = "task-comments";
    workProduct.review_decisions.forEach((decision) => {
      const item = document.createElement("li");
      const reviewer = decision.reviewer ? decision.reviewer.display_name : "Unknown identity";
      const meta = document.createElement("div");
      meta.className = "version-meta";
      const verb = decision.decision === "approved" ? "Approved" : "Returned for revision";
      meta.textContent = `${verb} by ${reviewer} · v${workProduct.versions.find((v) => v.id === decision.submission_version_id)?.version_number ?? "?"} · ${formatDate(decision.created_at)}`;
      item.appendChild(meta);
      if (decision.rationale) {
        const body = document.createElement("div");
        body.textContent = decision.rationale;
        item.appendChild(body);
      }
      historyList.appendChild(item);
    });
    li.appendChild(historyList);
  }

  if (task.status === "submitted") {
    const reviewForm = document.createElement("form");
    reviewForm.className = "task-review-form";
    const rationaleInput = document.createElement("textarea");
    rationaleInput.rows = 2;
    rationaleInput.maxLength = 4000;
    rationaleInput.placeholder = "Rationale (required to return for revision)";
    rationaleInput.setAttribute("aria-label", `Review rationale for ${workProduct.title}`);
    const approveButton = document.createElement("button");
    approveButton.type = "button";
    approveButton.textContent = "Approve";
    approveButton.addEventListener("click", () => reviewWorkProduct(task.id, workProduct.id, "approved", rationaleInput.value));
    const returnButton = document.createElement("button");
    returnButton.type = "button";
    returnButton.className = "button-secondary";
    returnButton.textContent = "Return for revision";
    returnButton.addEventListener("click", () => {
      if (!rationaleInput.value.trim()) {
        rationaleInput.focus();
        return;
      }
      reviewWorkProduct(task.id, workProduct.id, "returned", rationaleInput.value);
    });
    reviewForm.append(rationaleInput, approveButton, returnButton);
    li.appendChild(reviewForm);
  }

  const addVersionForm = document.createElement("form");
  addVersionForm.className = "task-add-version-form";
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.setAttribute("aria-label", `Replace ${workProduct.title} with a new version`);
  const addVersionButton = document.createElement("button");
  addVersionButton.type = "submit";
  addVersionButton.textContent = "Add version";
  addVersionForm.append(fileInput, addVersionButton);
  addVersionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!fileInput.files.length) return;
    await addWorkProductVersion(task.id, workProduct.id, fileInput.files[0]);
  });
  li.appendChild(addVersionForm);

  return li;
}

function renderTaskDetail(task) {
  const detail = document.createElement("div");
  detail.className = "task-detail";
  detail.hidden = true;

  if (task.description) {
    const descEl = document.createElement("p");
    descEl.className = "desc";
    descEl.textContent = task.description;
    detail.appendChild(descEl);
  }

  const controls = document.createElement("div");
  controls.className = "task-status-controls";

  const statusSelect = document.createElement("select");
  statusSelect.setAttribute("aria-label", `Status for ${task.title}`);
  ["open", "in_progress", "cancelled"].forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = TASK_STATUS_LABELS[value];
    if (value === task.status) option.selected = true;
    statusSelect.appendChild(option);
  });
  // "submitted"/"returned"/"approved" are set automatically (a
  // work-product submission or a review decision), never by this select -
  // shown, disabled, only when the task is currently in one of them, so
  // the pill and the dropdown never disagree about the task's own status.
  if (["submitted", "returned", "approved"].includes(task.status)) {
    const autoOption = document.createElement("option");
    autoOption.value = task.status;
    autoOption.textContent = TASK_STATUS_LABELS[task.status];
    autoOption.selected = true;
    autoOption.disabled = true;
    statusSelect.appendChild(autoOption);
  }
  statusSelect.addEventListener("change", () => updateTaskStatus(task.id, statusSelect.value));
  controls.appendChild(statusSelect);

  const assigneeSelect = document.createElement("select");
  assigneeSelect.setAttribute("aria-label", `Assignee for ${task.title}`);
  const unassignedOption = document.createElement("option");
  unassignedOption.value = "";
  unassignedOption.textContent = "Unassigned";
  assigneeSelect.appendChild(unassignedOption);
  devIdentities.forEach((devIdentity) => {
    const option = document.createElement("option");
    option.value = devIdentity.user.id;
    option.textContent = devIdentity.user.display_name;
    if (devIdentity.user.id === task.assigned_to) option.selected = true;
    assigneeSelect.appendChild(option);
  });
  assigneeSelect.addEventListener("change", () => reassignTask(task.id, assigneeSelect.value || null));
  controls.appendChild(assigneeSelect);
  detail.appendChild(controls);

  const commentsHeading = document.createElement("h4");
  commentsHeading.textContent = "Comments";
  detail.appendChild(commentsHeading);

  const commentsListEl = document.createElement("ul");
  commentsListEl.className = "task-comments";
  task.comments.forEach((comment) => {
    const item = document.createElement("li");
    const author = comment.author ? comment.author.display_name : "Unknown identity";
    const meta = document.createElement("div");
    meta.className = "version-meta";
    meta.textContent = `${author} · ${formatDate(comment.created_at)}`;
    const body = document.createElement("div");
    body.textContent = comment.body;
    item.append(meta, body);
    commentsListEl.appendChild(item);
  });
  detail.appendChild(commentsListEl);

  const commentForm = document.createElement("form");
  commentForm.className = "task-comment-form";
  const commentInput = document.createElement("textarea");
  commentInput.rows = 2;
  commentInput.maxLength = 4000;
  commentInput.setAttribute("aria-label", `Add a comment to ${task.title}`);
  const commentButton = document.createElement("button");
  commentButton.type = "submit";
  commentButton.textContent = "Add comment";
  commentForm.append(commentInput, commentButton);
  commentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!commentInput.value.trim()) return;
    await addTaskComment(task.id, commentInput.value);
  });
  detail.appendChild(commentForm);

  const workProductsHeading = document.createElement("h4");
  workProductsHeading.textContent = "Work products";
  detail.appendChild(workProductsHeading);

  const workProductsListEl = document.createElement("ul");
  workProductsListEl.className = "task-work-products";
  task.work_products.forEach((wp) => workProductsListEl.appendChild(renderWorkProduct(task, wp)));
  detail.appendChild(workProductsListEl);

  const newWorkProductForm = document.createElement("form");
  newWorkProductForm.className = "task-new-work-product-form";
  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.placeholder = "Work product title";
  titleInput.maxLength = 200;
  const wpFileInput = document.createElement("input");
  wpFileInput.type = "file";
  wpFileInput.setAttribute("aria-label", `Submit a work product for ${task.title}`);
  const submitButton = document.createElement("button");
  submitButton.type = "submit";
  submitButton.textContent = "Submit work product";
  newWorkProductForm.append(titleInput, wpFileInput, submitButton);
  newWorkProductForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!wpFileInput.files.length) return;
    await submitWorkProduct(task.id, titleInput.value, wpFileInput.files[0]);
  });
  detail.appendChild(newWorkProductForm);

  return detail;
}

function renderTask(task) {
  const li = document.createElement("li");
  li.className = "task-item";
  const isExpanded = expandedTaskIds.has(task.id);

  const header = document.createElement("div");
  header.className = "task-header";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "task-expand-toggle";
  toggle.setAttribute("aria-expanded", String(isExpanded));
  toggle.setAttribute("aria-label", `Expand details for ${task.title}`);
  const icon = document.createElement("span");
  icon.className = "task-expand-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "▸";
  const nameEl = document.createElement("span");
  nameEl.className = "name";
  nameEl.textContent = task.title;
  toggle.append(icon, nameEl);
  header.appendChild(toggle);

  const statusPill = document.createElement("span");
  statusPill.className = `task-status task-status-${task.status}`;
  statusPill.textContent = TASK_STATUS_LABELS[task.status] || task.status;
  header.appendChild(statusPill);
  li.appendChild(header);

  const meta = document.createElement("div");
  meta.className = "task-meta";
  const assigneeSpan = document.createElement("span");
  assigneeSpan.textContent = `Assignee: ${task.assigned_user ? task.assigned_user.display_name : "Unassigned"}`;
  meta.appendChild(assigneeSpan);
  if (task.workstream) {
    const workstreamSpan = document.createElement("span");
    workstreamSpan.textContent = ` · Workstream: ${task.workstream.name}`;
    meta.appendChild(workstreamSpan);
  }
  li.appendChild(meta);

  const detail = renderTaskDetail(task);
  detail.hidden = !isExpanded;
  li.appendChild(detail);

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    detail.hidden = expanded;
    if (expanded) expandedTaskIds.delete(task.id);
    else expandedTaskIds.add(task.id);
  });

  return li;
}

async function loadTasks() {
  await populateTaskFormOptions();
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tasks`);
  if (!res.ok) return;
  const list = await res.json();
  tasksListEl.textContent = "";
  tasksEmptyEl.hidden = list.length !== 0;
  list.forEach((task) => tasksListEl.appendChild(renderTask(task)));
}

async function updateTaskStatus(taskId, status) {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (res.ok) await loadTasks();
}

async function reassignTask(taskId, userId) {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assigned_to: userId }),
  });
  if (res.ok) await loadTasks();
}

async function addTaskComment(taskId, body) {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  if (res.ok) await loadTasks();
}

async function submitWorkProduct(taskId, title, file) {
  const formData = new FormData();
  formData.append("title", title);
  formData.append("file", file);
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/work-products`, {
    method: "POST",
    body: formData,
  });
  if (res.ok) {
    await loadTasks();
  } else {
    const body = await res.json().catch(() => ({}));
    window.alert(body.error || "Could not submit the work product.");
  }
}

async function addWorkProductVersion(taskId, workProductId, file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/work-products/${encodeURIComponent(workProductId)}/versions`, {
    method: "POST",
    body: formData,
  });
  if (res.ok) {
    await loadTasks();
    return;
  }
  const body = await res.json().catch(() => ({}));
  if (res.status === 409) {
    window.alert("That file is identical to the current version - nothing to replace.");
  } else {
    window.alert(body.error || "Could not upload a new version.");
  }
}

async function reviewWorkProduct(taskId, workProductId, decision, rationale) {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/work-products/${encodeURIComponent(workProductId)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, rationale }),
  });
  if (res.ok) {
    await loadTasks();
    return;
  }
  const body = await res.json().catch(() => ({}));
  window.alert(body.error || "Could not record the review decision.");
}

taskFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  taskErrorEl.textContent = "";
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: taskTitleInputEl.value,
      description: taskDescriptionInputEl.value,
      workstream_id: taskWorkstreamSelectEl.value || null,
      assigned_to: taskAssigneeSelectEl.value || null,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    taskErrorEl.textContent = body.error || "Could not create the task.";
    return;
  }
  taskTitleInputEl.value = "";
  taskDescriptionInputEl.value = "";
  taskWorkstreamSelectEl.value = "";
  taskAssigneeSelectEl.value = "";
  await loadTasks();
});

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

async function uploadNewVersion(doc, file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(doc.id)}/versions`,
    { method: "POST", body: formData }
  );

  if (res.ok) {
    await loadDocuments();
    return;
  }
  const body = await res.json().catch(() => ({}));
  if (res.status === 409) {
    window.alert("That file is identical to the current version - nothing to replace.");
  } else {
    window.alert(body.error || "Could not upload a new version.");
  }
}

// Task 13.1: generalized from a documents-only helper so work-product
// submission versions (a different table, a different download route -
// see work_products.py) can reuse the exact same dialog/markup instead of
// a second, near-identical one.
async function openVersionsDialog({ name, listUrl, downloadUrlFor, currentVersionId }) {
  versionsDialogNameEl.textContent = name;
  versionsListEl.textContent = "";

  const res = await fetch(listUrl);
  const versions = res.ok ? await res.json() : [];

  versions
    .slice()
    .reverse()
    .forEach((version) => {
      const item = document.createElement("li");

      const meta = document.createElement("span");
      meta.className = "version-meta";
      const current = version.id === currentVersionId ? " (current)" : "";
      meta.textContent = `v${version.version_number}${current} · ${formatSize(version.size_bytes)} · ${formatDate(version.uploaded_at)}`;

      const downloadLink = document.createElement("a");
      downloadLink.className = "link-action";
      downloadLink.textContent = "Download";
      downloadLink.href = downloadUrlFor(version);

      item.append(meta, downloadLink);
      versionsListEl.append(item);
    });

  versionsDialogEl.showModal();
}

closeVersionsButtonEl.addEventListener("click", () => versionsDialogEl.close());

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
  if (projectId) {
    loadDocuments();
    loadReconciliations();
    loadBrief();
    loadWorkstreams();
    loadMemberships();
    loadTasks();
  }
});
