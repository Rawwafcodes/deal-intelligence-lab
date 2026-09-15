// Validation case detail page: private answer-key editor (issues +
// must-not-claim items), locking, and running the blind cross-format
// reconciliation (fresh, or attaching an already-completed analysis).

const breadcrumbEl = document.getElementById("app-breadcrumb");
const caseMetaCardEl = document.getElementById("case-meta-card");
const answerKeyCardEl = document.getElementById("answer-key-card");
const answerKeyLockedBannerEl = document.getElementById("answer-key-locked-banner");
const issuesListEl = document.getElementById("issues-list");
const mustNotClaimListEl = document.getElementById("must-not-claim-list");
const addIssueButtonEl = document.getElementById("add-issue-button");
const addMustNotClaimButtonEl = document.getElementById("add-must-not-claim-button");
const answerKeyErrorEl = document.getElementById("answer-key-error");
const answerKeyActionsEl = document.getElementById("answer-key-actions");
const saveDraftButtonEl = document.getElementById("save-draft-button");
const lockButtonEl = document.getElementById("lock-button");
const reviseButtonEl = document.getElementById("revise-button");
const runCardEl = document.getElementById("run-card");
const runHintEl = document.getElementById("run-hint");
const startRunButtonEl = document.getElementById("start-run-button");
const attachExistingButtonEl = document.getElementById("attach-existing-button");
const runErrorEl = document.getElementById("run-error");
const runsCardEl = document.getElementById("runs-card");
const runsTbodyEl = document.getElementById("runs-tbody");
const runConfirmDialogEl = document.getElementById("run-confirm-dialog");
const runConfirmFormEl = document.getElementById("run-confirm-form");
const runConfirmTextEl = document.getElementById("run-confirm-text");
const runConfirmListEl = document.getElementById("run-confirm-list");
const runConfirmErrorEl = document.getElementById("run-confirm-error");
const cancelRunConfirmEl = document.getElementById("cancel-run-confirm");
const sendRunConfirmEl = document.getElementById("send-run-confirm");
const attachExistingDialogEl = document.getElementById("attach-existing-dialog");
const attachExistingFormEl = document.getElementById("attach-existing-form");
const existingAnalysisSelectEl = document.getElementById("existing-analysis-select");
const attachExistingErrorEl = document.getElementById("attach-existing-error");
const cancelAttachExistingEl = document.getElementById("cancel-attach-existing");
const lockConfirmDialogEl = document.getElementById("lock-confirm-dialog");
const lockConfirmFormEl = document.getElementById("lock-confirm-form");
const lockConfirmErrorEl = document.getElementById("lock-confirm-error");
const cancelLockConfirmEl = document.getElementById("cancel-lock-confirm");
const reviseConfirmDialogEl = document.getElementById("revise-confirm-dialog");
const reviseConfirmFormEl = document.getElementById("revise-confirm-form");
const reviseConfirmErrorEl = document.getElementById("revise-confirm-error");
const cancelReviseConfirmEl = document.getElementById("cancel-revise-confirm");

const params = new URLSearchParams(window.location.search);
const projectId = params.get("project");
const caseId = params.get("case");

function formatDate(isoString) {
  if (!isoString) return "—";
  const d = new Date(isoString);
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function setBreadcrumb(projectName, caseName) {
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
  const labLink = document.createElement("a");
  labLink.href = `/validation.html?project=${encodeURIComponent(projectId)}`;
  labLink.textContent = "Validation Lab";
  const sep3 = document.createElement("span");
  sep3.className = "sep";
  sep3.textContent = "/";
  const current = document.createElement("span");
  current.className = "current";
  current.textContent = caseName;
  breadcrumbEl.append(homeLink, sep1, projectLink, sep2, labLink, sep3, current);
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
closeOnBackdropClick(runConfirmDialogEl);
closeOnBackdropClick(attachExistingDialogEl);
closeOnBackdropClick(lockConfirmDialogEl);
closeOnBackdropClick(reviseConfirmDialogEl);

const CLASSIFICATIONS = [
  "cross-source conflict",
  "unsupported model assumption",
  "missing evidence",
  "calculation or formula concern",
  "definition/methodology mismatch",
  "timing or period mismatch",
];
const SEVERITIES = ["critical", "high", "medium", "low", "informational"];

let caseData = null;
let answerKeyData = null;
let issues = [];
let mustNotClaim = [];
let latestDocuments = [];

function uid() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function makeField(labelText, value, onChange, opts = {}) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const label = document.createElement("label");
  label.textContent = labelText;
  wrap.appendChild(label);
  let input;
  if (opts.select) {
    input = document.createElement("select");
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "—";
    input.appendChild(blank);
    opts.select.forEach((optValue) => {
      const opt = document.createElement("option");
      opt.value = optValue;
      opt.textContent = optValue;
      input.appendChild(opt);
    });
    input.value = value || "";
  } else if (opts.textarea) {
    input = document.createElement("textarea");
    input.rows = opts.rows || 2;
    input.value = value || "";
  } else {
    input = document.createElement("input");
    input.type = "text";
    input.value = value || "";
  }
  input.disabled = !!opts.disabled;
  input.addEventListener("input", () => onChange(input.value));
  input.addEventListener("change", () => onChange(input.value));
  wrap.appendChild(input);
  return wrap;
}

function renderIssues(locked) {
  issuesListEl.textContent = "";
  issues.forEach((issue, index) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "12px";

    const header = document.createElement("div");
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.alignItems = "center";
    const title = document.createElement("strong");
    title.textContent = `Issue ${index + 1}`;
    header.appendChild(title);
    if (!locked) {
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "link-action danger";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", () => {
        issues.splice(index, 1);
        renderIssues(locked);
      });
      header.appendChild(removeBtn);
    }
    card.appendChild(header);

    card.appendChild(makeField("Title", issue.title, (v) => (issue.title = v), { disabled: locked }));
    card.appendChild(
      makeField("Description", issue.description, (v) => (issue.description = v), { textarea: true, disabled: locked })
    );
    card.appendChild(
      makeField(
        "Expected classification",
        issue.expected_classification,
        (v) => (issue.expected_classification = v),
        { select: CLASSIFICATIONS, disabled: locked }
      )
    );
    card.appendChild(
      makeField("Expected severity", issue.expected_severity, (v) => (issue.expected_severity = v), {
        select: SEVERITIES,
        disabled: locked,
      })
    );
    card.appendChild(
      makeField("Why material", issue.materiality, (v) => (issue.materiality = v), { textarea: true, disabled: locked })
    );
    card.appendChild(
      makeField("Known supporting source", issue.known_source, (v) => (issue.known_source = v), { disabled: locked })
    );
    card.appendChild(
      makeField("Known page/sheet/cell/formula", issue.known_location, (v) => (issue.known_location = v), {
        disabled: locked,
      })
    );
    card.appendChild(
      makeField("Expected calculation or corrected value", issue.expected_value, (v) => (issue.expected_value = v), {
        disabled: locked,
      })
    );
    card.appendChild(
      makeField("Notes for evaluator", issue.evaluator_notes, (v) => (issue.evaluator_notes = v), {
        textarea: true,
        disabled: locked,
      })
    );

    issuesListEl.appendChild(card);
  });
}

function renderMustNotClaim(locked) {
  mustNotClaimListEl.textContent = "";
  mustNotClaim.forEach((item, index) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "12px";

    const header = document.createElement("div");
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.alignItems = "center";
    const title = document.createElement("strong");
    title.textContent = `Must-not-claim ${index + 1}`;
    header.appendChild(title);
    if (!locked) {
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "link-action danger";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", () => {
        mustNotClaim.splice(index, 1);
        renderMustNotClaim(locked);
      });
      header.appendChild(removeBtn);
    }
    card.appendChild(header);

    card.appendChild(makeField("Statement", item.statement, (v) => (item.statement = v), { disabled: locked }));
    card.appendChild(makeField("Notes", item.notes, (v) => (item.notes = v), { textarea: true, disabled: locked }));

    mustNotClaimListEl.appendChild(card);
  });
}

addIssueButtonEl.addEventListener("click", () => {
  issues.push({
    id: uid(),
    title: "",
    description: "",
    expected_classification: "",
    expected_severity: "",
    materiality: "",
    known_source: "",
    known_location: "",
    expected_value: "",
    evaluator_notes: "",
  });
  renderIssues(false);
});

addMustNotClaimButtonEl.addEventListener("click", () => {
  mustNotClaim.push({ id: uid(), statement: "", notes: "" });
  renderMustNotClaim(false);
});

function renderAnswerKeyState() {
  const locked = answerKeyData && answerKeyData.is_locked;

  if (locked) {
    answerKeyLockedBannerEl.hidden = false;
    const hiddenNote = answerKeyData.content_hidden
      ? " Hidden from this page until a validation run against it completes, to preserve blindness."
      : "";
    answerKeyLockedBannerEl.textContent =
      `Locked at ${formatDate(answerKeyData.locked_at)}. Checksum: ${answerKeyData.checksum}.` + hiddenNote;
    answerKeyActionsEl.hidden = true;
    reviseButtonEl.hidden = false;
    addIssueButtonEl.hidden = true;
    addMustNotClaimButtonEl.hidden = true;
  } else {
    answerKeyLockedBannerEl.hidden = true;
    answerKeyActionsEl.hidden = false;
    reviseButtonEl.hidden = true;
    addIssueButtonEl.hidden = false;
    addMustNotClaimButtonEl.hidden = false;
  }

  if (answerKeyData && answerKeyData.content) {
    issues = answerKeyData.content.issues || [];
    mustNotClaim = answerKeyData.content.must_not_claim || [];
  } else if (!locked) {
    issues = issues || [];
    mustNotClaim = mustNotClaim || [];
  } else {
    issues = [];
    mustNotClaim = [];
  }

  renderIssues(!!locked);
  renderMustNotClaim(!!locked);
}

saveDraftButtonEl.addEventListener("click", async () => {
  answerKeyErrorEl.textContent = "";
  saveDraftButtonEl.disabled = true;
  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(caseId)}/answer-key`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: { issues, must_not_claim: mustNotClaim } }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      answerKeyErrorEl.textContent = (payload && payload.error) || "Could not save the draft.";
      return;
    }
    answerKeyData = payload;
    renderAnswerKeyState();
  } finally {
    saveDraftButtonEl.disabled = false;
  }
});

lockButtonEl.addEventListener("click", () => {
  lockConfirmErrorEl.textContent = "";
  lockConfirmDialogEl.showModal();
});

cancelLockConfirmEl.addEventListener("click", () => lockConfirmDialogEl.close());

lockConfirmFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  lockConfirmErrorEl.textContent = "";
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(caseId)}/answer-key/lock`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) }
  );
  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    lockConfirmErrorEl.textContent = (payload && payload.error) || "Could not lock the answer key.";
    return;
  }
  lockConfirmDialogEl.close();
  answerKeyData = payload;
  renderAnswerKeyState();
  updateRunAvailability();
});

reviseButtonEl.addEventListener("click", () => {
  reviseConfirmErrorEl.textContent = "";
  reviseConfirmDialogEl.showModal();
});

cancelReviseConfirmEl.addEventListener("click", () => reviseConfirmDialogEl.close());

reviseConfirmFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  reviseConfirmErrorEl.textContent = "";
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(caseId)}/answer-key/revise`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) }
  );
  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    reviseConfirmErrorEl.textContent = (payload && payload.error) || "Could not create a revision.";
    return;
  }
  reviseConfirmDialogEl.close();
  answerKeyData = payload;
  answerKeyData.content_hidden = false;
  renderAnswerKeyState();
  updateRunAvailability();
});

function updateRunAvailability() {
  const locked = answerKeyData && answerKeyData.is_locked;
  runCardEl.hidden = false;
  startRunButtonEl.disabled = !locked;
  attachExistingButtonEl.disabled = !locked;
  runHintEl.textContent = locked
    ? "The answer key is locked. Running now qualifies as a genuinely blind test."
    : "Lock the answer key before a run can start.";
}

startRunButtonEl.addEventListener("click", async () => {
  runErrorEl.textContent = "";
  const docsRes = await fetch(`/api/projects/${encodeURIComponent(projectId)}/documents`);
  const docs = docsRes.ok ? await docsRes.json() : [];
  const selectedIds = new Set([...caseData.pdf_document_ids, ...caseData.excel_document_ids]);
  const selectedDocs = docs.filter((d) => selectedIds.has(d.id));

  runConfirmTextEl.textContent =
    "These files will be sent to Anthropic for the normal cross-format reconciliation. The answer key is never included.";
  runConfirmListEl.textContent = "";
  selectedDocs.forEach((doc) => {
    const item = document.createElement("li");
    item.textContent = doc.original_filename;
    runConfirmListEl.appendChild(item);
  });
  runConfirmErrorEl.textContent = "";
  sendRunConfirmEl.disabled = false;
  sendRunConfirmEl.textContent = "Send to Claude";
  runConfirmDialogEl.showModal();
});

cancelRunConfirmEl.addEventListener("click", () => runConfirmDialogEl.close());

runConfirmFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  runConfirmErrorEl.textContent = "";
  sendRunConfirmEl.disabled = true;
  sendRunConfirmEl.textContent = "Analyzing… this can take several minutes";
  try {
    const res = await fetch(
      `/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(caseId)}/runs`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true, mode: "new" }),
      }
    );
    const payload = await res.json().catch(() => null);
    if (!payload || !payload.id) {
      runConfirmErrorEl.textContent = (payload && payload.error) || "The run failed to start.";
      return;
    }
    window.location.href = `/validation-evaluation.html?project=${encodeURIComponent(projectId)}&case=${encodeURIComponent(caseId)}&run=${encodeURIComponent(payload.id)}`;
  } catch (err) {
    runConfirmErrorEl.textContent = "Could not reach the local app server.";
  } finally {
    sendRunConfirmEl.disabled = false;
    sendRunConfirmEl.textContent = "Send to Claude";
  }
});

attachExistingButtonEl.addEventListener("click", async () => {
  attachExistingErrorEl.textContent = "";
  existingAnalysisSelectEl.textContent = "";
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/cross-format-analyses`);
  const records = res.ok ? await res.json() : [];
  if (records.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "No existing analyses in this project";
    opt.disabled = true;
    existingAnalysisSelectEl.appendChild(opt);
  }
  records.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = `${formatDate(r.created_at)} — ${r.pdf_document_filenames.join(", ")} + ${r.excel_document_filenames.join(", ")} (${r.status})`;
    existingAnalysisSelectEl.appendChild(opt);
  });
  attachExistingDialogEl.showModal();
});

cancelAttachExistingEl.addEventListener("click", () => attachExistingDialogEl.close());

attachExistingFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  attachExistingErrorEl.textContent = "";
  const analysisId = existingAnalysisSelectEl.value;
  if (!analysisId) {
    attachExistingErrorEl.textContent = "Select an analysis to attach.";
    return;
  }
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(caseId)}/runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true, mode: "existing", cross_format_analysis_id: analysisId }),
    }
  );
  const payload = await res.json().catch(() => null);
  if (!payload || !payload.id) {
    attachExistingErrorEl.textContent = (payload && payload.error) || "Could not attach the analysis.";
    return;
  }
  window.location.href = `/validation-evaluation.html?project=${encodeURIComponent(projectId)}&case=${encodeURIComponent(caseId)}&run=${encodeURIComponent(payload.id)}`;
});

function renderRuns(runs) {
  runsCardEl.hidden = runs.length === 0;
  runsTbodyEl.textContent = "";
  runs.forEach((run) => {
    const row = document.createElement("tr");

    const idCell = document.createElement("td");
    idCell.textContent = run.id.slice(0, 8);

    const blindCell = document.createElement("td");
    blindCell.textContent = run.is_blind ? "Blind" : "Retrospective";

    const startedCell = document.createElement("td");
    startedCell.className = "muted";
    startedCell.textContent = formatDate(run.started_at);

    const actionsCell = document.createElement("td");
    const link = document.createElement("a");
    link.className = "link-action";
    link.href = `/validation-evaluation.html?project=${encodeURIComponent(projectId)}&case=${encodeURIComponent(caseId)}&run=${encodeURIComponent(run.id)}`;
    link.textContent = "Evaluate";
    actionsCell.appendChild(link);

    row.append(idCell, blindCell, startedCell, actionsCell);
    runsTbodyEl.appendChild(row);
  });
}

function renderCaseMeta() {
  caseMetaCardEl.textContent = "";
  const title = document.createElement("div");
  title.className = "name";
  title.textContent = caseData.name;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `Created ${formatDate(caseData.created_at)}`;
  const desc = document.createElement("div");
  desc.className = "description";
  desc.textContent = caseData.description || "No description provided.";
  caseMetaCardEl.append(title, meta, desc);
}

async function load() {
  const [projectRes, detailRes] = await Promise.all([
    fetch(`/api/projects/${encodeURIComponent(projectId)}`),
    fetch(`/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(caseId)}`),
  ]);

  if (!detailRes.ok) {
    caseMetaCardEl.textContent = "Validation case not found.";
    return;
  }
  const detail = await detailRes.json();
  caseData = detail.case;
  answerKeyData = detail.answer_key;

  setBreadcrumb(projectRes.ok ? (await projectRes.json()).name : "Project", caseData.name);
  renderCaseMeta();

  answerKeyCardEl.hidden = false;
  renderAnswerKeyState();
  updateRunAvailability();
  renderRuns(detail.runs);
}

if (projectId && caseId) load();
