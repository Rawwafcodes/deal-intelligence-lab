// Validation Lab list page: shows every validation case for a project and
// lets the user create a new one (name, description, document selection).

const breadcrumbEl = document.getElementById("app-breadcrumb");
const newCaseButtonEl = document.getElementById("new-case-button");
const newCaseDialogEl = document.getElementById("new-case-dialog");
const newCaseFormEl = document.getElementById("new-case-form");
const newCaseNameEl = document.getElementById("case-name");
const newCaseDescriptionEl = document.getElementById("case-description");
const newCaseDocListEl = document.getElementById("new-case-doc-list");
const newCaseErrorEl = document.getElementById("new-case-error");
const cancelNewCaseButtonEl = document.getElementById("cancel-new-case");
const casesTbodyEl = document.getElementById("cases-tbody");
const casesEmptyEl = document.getElementById("cases-empty");

const params = new URLSearchParams(window.location.search);
const projectId = params.get("project");

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

function setBreadcrumb(projectName) {
  breadcrumbEl.textContent = "";
  const homeLink = document.createElement("a");
  homeLink.href = "/";
  homeLink.textContent = "Home";
  const sep1 = document.createElement("span");
  sep1.className = "sep";
  sep1.textContent = "/";
  const projectLink = document.createElement("a");
  projectLink.href = `/project.html?id=${encodeURIComponent(projectId)}`;
  projectLink.textContent = projectName;
  const sep2 = document.createElement("span");
  sep2.className = "sep";
  sep2.textContent = "/";
  const current = document.createElement("span");
  current.className = "current";
  current.textContent = "Validation Lab";
  breadcrumbEl.append(homeLink, sep1, projectLink, sep2, current);
}

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
closeOnBackdropClick(newCaseDialogEl);

let latestDocuments = [];

async function loadDocumentsForPicker() {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/documents`);
  if (!res.ok) return;
  latestDocuments = await res.json();
}

function renderDocPicker() {
  newCaseDocListEl.textContent = "";
  latestDocuments
    .filter((d) => d.extension === ".pdf" || d.extension === ".xlsx" || d.extension === ".xls")
    .forEach((doc) => {
      const item = document.createElement("li");
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = doc.id;
      checkbox.dataset.extension = doc.extension;
      const typeLabel = doc.extension === ".pdf" ? "PDF" : doc.extension.replace(".", "").toUpperCase();
      const text = document.createElement("span");
      text.textContent = `[${typeLabel}] ${doc.original_filename}`;
      label.append(checkbox, text);
      item.appendChild(label);
      newCaseDocListEl.appendChild(item);
    });
}

newCaseButtonEl.addEventListener("click", async () => {
  newCaseErrorEl.textContent = "";
  newCaseFormEl.reset();
  await loadDocumentsForPicker();
  renderDocPicker();
  newCaseDialogEl.showModal();
});
cancelNewCaseButtonEl.addEventListener("click", () => newCaseDialogEl.close());

newCaseFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  newCaseErrorEl.textContent = "";

  const checked = Array.from(newCaseDocListEl.querySelectorAll("input[type=checkbox]:checked"));
  const pdfIds = checked.filter((c) => c.dataset.extension === ".pdf").map((c) => c.value);
  const excelIds = checked.filter((c) => c.dataset.extension !== ".pdf").map((c) => c.value);

  if (pdfIds.length < 1 || excelIds.length < 1) {
    newCaseErrorEl.textContent = "Select at least one PDF and one Excel workbook.";
    return;
  }

  const submitButton = document.getElementById("create-case-button");
  submitButton.disabled = true;
  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/validation-cases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: newCaseNameEl.value,
        description: newCaseDescriptionEl.value,
        pdf_document_ids: pdfIds,
        excel_document_ids: excelIds,
      }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok || !payload || !payload.id) {
      newCaseErrorEl.textContent = (payload && payload.error) || "Could not create the validation case.";
      return;
    }
    window.location.href = `/validation-case.html?project=${encodeURIComponent(projectId)}&case=${encodeURIComponent(payload.id)}`;
  } catch (err) {
    newCaseErrorEl.textContent = "Could not reach the local app server.";
  } finally {
    submitButton.disabled = false;
  }
});

function answerKeyStatusLabel(caseSummary) {
  return caseSummary.answer_key_locked ? "Locked" : "Draft";
}

function renderCases(cases) {
  casesTbodyEl.textContent = "";
  casesEmptyEl.hidden = cases.length !== 0;

  cases.forEach((c) => {
    const row = document.createElement("tr");

    const nameCell = document.createElement("td");
    const nameLink = document.createElement("a");
    nameLink.href = `/validation-case.html?project=${encodeURIComponent(projectId)}&case=${encodeURIComponent(c.id)}`;
    nameLink.textContent = c.name;
    nameCell.appendChild(nameLink);

    const keyCell = document.createElement("td");
    keyCell.textContent = answerKeyStatusLabel(c);

    const runsCell = document.createElement("td");
    runsCell.textContent = String(c.run_count);

    const createdCell = document.createElement("td");
    createdCell.className = "muted";
    createdCell.textContent = formatDate(c.created_at);

    const actionsCell = document.createElement("td");
    const openLink = document.createElement("a");
    openLink.className = "link-action";
    openLink.href = nameLink.href;
    openLink.textContent = "Open";
    actionsCell.appendChild(openLink);

    row.append(nameCell, keyCell, runsCell, createdCell, actionsCell);
    casesTbodyEl.appendChild(row);
  });
}

async function loadCases() {
  const [projectRes, casesRes] = await Promise.all([
    fetch(`/api/projects/${encodeURIComponent(projectId)}`),
    fetch(`/api/projects/${encodeURIComponent(projectId)}/validation-cases`),
  ]);

  setBreadcrumb(projectRes.ok ? (await projectRes.json()).name : "Project");
  if (!casesRes.ok) return;

  const cases = await casesRes.json();
  const summaries = await Promise.all(
    cases.map(async (c) => {
      const [detailRes, runsRes] = await Promise.all([
        fetch(`/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(c.id)}`),
        fetch(`/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(c.id)}/runs`),
      ]);
      const detail = detailRes.ok ? await detailRes.json() : null;
      const runs = runsRes.ok ? await runsRes.json() : [];
      return {
        ...c,
        answer_key_locked: detail && detail.answer_key ? detail.answer_key.is_locked : false,
        run_count: runs.length,
      };
    })
  );
  renderCases(summaries);
}

if (projectId) loadCases();
