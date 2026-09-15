// Deal Workspace (Milestone 9): turns one completed cross-format
// reconciliation into a reviewable, filterable findings register, an
// information-request list, and an executive memo. AI finding content
// (title, classification, severity, explanation, evidence, citations) is
// always read-only here - only the workflow fields next to it are
// editable. See workspaces.py for why: AI content is re-derived from the
// immutable analysis record on every load, never stored by this page.

const breadcrumbEl = document.getElementById("app-breadcrumb");
const loadingCardEl = document.getElementById("workspace-loading-card");
const errorCardEl = document.getElementById("workspace-error-card");
const errorTextEl = document.getElementById("workspace-error-text");
const contentEl = document.getElementById("workspace-content");
const titleEl = document.getElementById("workspace-title");
const subtitleEl = document.getElementById("workspace-subtitle");
const summaryStripEl = document.getElementById("workspace-summary-strip");

const params = new URLSearchParams(window.location.search);
const projectId = params.get("project");
const workspaceId = params.get("workspace");

const SEVERITIES = ["critical", "high", "medium", "low", "informational"];
const SEVERITY_LABELS = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  informational: "Informational",
  unspecified: "Unspecified",
};
const REVIEW_STATUSES = ["unreviewed", "accepted", "partially_accepted", "rejected", "unverifiable"];
const REVIEW_STATUS_LABELS = {
  unreviewed: "Unreviewed",
  accepted: "Accepted",
  partially_accepted: "Partially accepted",
  rejected: "Rejected",
  unverifiable: "Unverifiable",
};
const RESOLUTION_STATUSES = ["open", "awaiting_information", "management_responded", "resolved", "accepted_risk"];
const RESOLUTION_STATUS_LABELS = {
  open: "Open",
  awaiting_information: "Awaiting information",
  management_responded: "Management responded",
  resolved: "Resolved",
  accepted_risk: "Accepted risk",
};
const REQUEST_PRIORITIES = ["low", "medium", "high"];
const REQUEST_STATUSES = ["draft", "sent", "answered", "closed"];
const REQUEST_STATUS_LABELS = { draft: "Draft", sent: "Sent", answered: "Answered", closed: "Closed" };
const MEMO_RECOMMENDATIONS = [
  "no_conclusion",
  "proceed",
  "proceed_with_conditions",
  "pause_pending_information",
  "do_not_proceed",
];
const MEMO_RECOMMENDATION_LABELS = {
  no_conclusion: "No conclusion yet",
  proceed: "Proceed",
  proceed_with_conditions: "Proceed with conditions",
  pause_pending_information: "Pause pending information",
  do_not_proceed: "Do not proceed",
};

let report = null; // { workspace, analysis, findings, summary }
let documentsById = new Map();
let requestsState = [];
let memoState = null;
let expandedFindingId = null;
let editValuesByFindingId = new Map();

const filters = {
  search: "",
  severity: "all",
  classification: "all",
  reviewStatus: "all",
  resolutionStatus: "all",
  sourceDocument: "all",
  owner: "all",
  showDuplicates: false,
};
const sortState = { key: "effective_severity", dir: "asc" };

function apiBase() {
  return `/api/projects/${encodeURIComponent(projectId)}/workspaces/${encodeURIComponent(workspaceId)}`;
}

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
  current.textContent = "Deal workspace";
  breadcrumbEl.append(homeLink, sep1, projectLink, sep2, current);
}

function fillSelect(select, options, { includeBlank } = {}) {
  select.textContent = "";
  if (includeBlank) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Not set";
    select.appendChild(opt);
  }
  options.forEach(([value, label]) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
  });
}

// -- data loading ---------------------------------------------------------

async function loadWorkspace() {
  const res = await fetch(apiBase());
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error((payload && payload.error) || "Could not load this workspace.");
  }
  report = await res.json();
}

async function loadRequests() {
  const res = await fetch(`${apiBase()}/requests`);
  requestsState = res.ok ? await res.json() : [];
}

async function loadMemo() {
  const res = await fetch(`${apiBase()}/memo`);
  memoState = res.ok ? await res.json() : null;
}

async function loadDocuments() {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/documents`);
  const docs = res.ok ? await res.json() : [];
  documentsById = new Map(docs.map((d) => [d.id, d]));
}

async function refreshAll() {
  await Promise.all([loadWorkspace(), loadRequests(), loadMemo()]);
  renderSummary();
  populateFilterOptions();
  renderFindings();
  renderRequests();
  renderMemo();
}

// -- summary strip ----------------------------------------------------------

function metricTile(value, label, variant) {
  const div = document.createElement("div");
  div.className = `ws-metric${variant ? ` ws-metric-${variant}` : ""}`;
  const v = document.createElement("div");
  v.className = "ws-metric-value";
  v.textContent = value;
  const l = document.createElement("div");
  l.className = "ws-metric-label";
  l.textContent = label;
  div.append(v, l);
  return div;
}

function renderSummary() {
  const { analysis, summary } = report;
  titleEl.textContent = `${report.__projectName || "Deal"} workspace`;
  subtitleEl.textContent =
    `Linked to reconciliation run ${formatDate(analysis.created_at)} · ${summary.pdf_document_count} PDF, ` +
    `${summary.excel_document_count} Excel source document(s) · ${summary.model}`;

  summaryStripEl.textContent = "";
  summaryStripEl.append(
    metricTile(summary.document_count, "Source documents"),
    metricTile(
      summary.input_tokens != null ? `${summary.input_tokens.toLocaleString()} / ${summary.output_tokens.toLocaleString()}` : "—",
      "Tokens in / out"
    ),
    metricTile(summary.total_findings, "Total findings"),
    metricTile(summary.by_severity.critical || 0, "Critical", "critical"),
    metricTile(summary.by_severity.high || 0, "High"),
    metricTile(summary.open_critical_high_count, "Open critical/high", "attention"),
    metricTile(summary.awaiting_management_response_count, "Awaiting response", "attention"),
    metricTile(summary.by_origin.human || 0, "Human-added"),
    metricTile(summary.duplicate_count, "Duplicates (hidden)"),
    metricTile(summary.request_count, "Information requests")
  );
}

// -- filters ------------------------------------------------------------

function sourceDocumentOptionsForAnalysis() {
  const { analysis } = report;
  const options = [];
  analysis.pdf_document_ids.forEach((id, i) => options.push([id, analysis.pdf_document_filenames[i]]));
  analysis.excel_document_ids.forEach((id, i) => options.push([id, analysis.excel_document_filenames[i]]));
  return options;
}

function populateFilterOptions() {
  fillSelect(document.getElementById("filter-severity"), [
    ["all", "All"],
    ...SEVERITIES.map((s) => [s, SEVERITY_LABELS[s]]),
    ["unspecified", "Unspecified"],
  ]);
  const classifications = Array.from(new Set(report.findings.map((f) => f.classification).filter(Boolean))).sort();
  fillSelect(document.getElementById("filter-classification"), [
    ["all", "All"],
    ...classifications.map((c) => [c, c]),
  ]);
  fillSelect(document.getElementById("filter-review-status"), [
    ["all", "All"],
    ...REVIEW_STATUSES.map((s) => [s, REVIEW_STATUS_LABELS[s]]),
  ]);
  fillSelect(document.getElementById("filter-resolution-status"), [
    ["all", "All"],
    ...RESOLUTION_STATUSES.map((s) => [s, RESOLUTION_STATUS_LABELS[s]]),
  ]);
  fillSelect(document.getElementById("filter-source-document"), [
    ["all", "All"],
    ...sourceDocumentOptionsForAnalysis(),
  ]);
  const owners = Array.from(new Set(report.findings.map((f) => f.assigned_owner).filter(Boolean))).sort();
  fillSelect(document.getElementById("filter-owner"), [["all", "All"], ...owners.map((o) => [o, o])]);

  document.getElementById("filter-search").value = filters.search;
  document.getElementById("filter-severity").value = filters.severity;
  document.getElementById("filter-classification").value = filters.classification;
  document.getElementById("filter-review-status").value = filters.reviewStatus;
  document.getElementById("filter-resolution-status").value = filters.resolutionStatus;
  document.getElementById("filter-source-document").value = filters.sourceDocument;
  document.getElementById("filter-owner").value = filters.owner;
  document.getElementById("filter-show-duplicates").checked = filters.showDuplicates;
}

function findingReferencesDocument(finding, documentId) {
  if ((finding.pdf_citations || []).some((c) => c.document_id === documentId)) return true;
  if ((finding.excel_citations || []).some((c) => c.document_id === documentId)) return true;
  if ((finding.evidence_document_ids || []).includes(documentId)) return true;
  return false;
}

const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3, informational: 4, unspecified: 5 };

function visibleFindings() {
  const search = filters.search.trim().toLowerCase();
  let list = report.findings.filter((f) => {
    if (!filters.showDuplicates && f.is_duplicate) return false;
    const severityKey = (f.effective_severity || "unspecified").toLowerCase();
    if (filters.severity !== "all" && severityKey !== filters.severity) return false;
    if (filters.classification !== "all" && f.classification !== filters.classification) return false;
    if (filters.reviewStatus !== "all" && f.review_status !== filters.reviewStatus) return false;
    if (filters.resolutionStatus !== "all" && f.resolution_status !== filters.resolutionStatus) return false;
    if (filters.owner !== "all" && f.assigned_owner !== filters.owner) return false;
    if (filters.sourceDocument !== "all" && !findingReferencesDocument(f, filters.sourceDocument)) return false;
    if (search) {
      const haystack = `${f.title} ${f.explanation}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });

  const { key, dir } = sortState;
  list = list.slice().sort((a, b) => {
    let av, bv;
    if (key === "effective_severity") {
      av = SEVERITY_RANK[(a.effective_severity || "unspecified").toLowerCase()] ?? 9;
      bv = SEVERITY_RANK[(b.effective_severity || "unspecified").toLowerCase()] ?? 9;
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

// -- findings table -------------------------------------------------------

function severityBadge(severityKey) {
  const key = (severityKey || "unspecified").toLowerCase();
  const badge = document.createElement("span");
  badge.className = `ws-severity-badge ws-severity-${key}`;
  badge.textContent = SEVERITY_LABELS[key] || key;
  return badge;
}

function statusBadge(text, extraClass) {
  const badge = document.createElement("span");
  badge.className = `ws-status-badge${extraClass ? ` ${extraClass}` : ""}`;
  badge.textContent = text;
  return badge;
}

function renderPdfCitations(container, citations) {
  (citations || []).forEach((c) => {
    const link = document.createElement("a");
    link.className = "citation-badge";
    link.target = "_blank";
    link.rel = "noopener";
    if (c.document_id) {
      link.href = `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(c.document_id)}/download?inline=1#page=${c.start_page}`;
    } else {
      link.removeAttribute("target");
      link.classList.add("citation-badge-unresolved");
    }
    link.title = `${c.document_title || "document"} — ${c.cited_text || ""}`;
    const pageLabel = c.end_page && c.end_page !== c.start_page ? `p.${c.start_page}-${c.end_page}` : `p.${c.start_page}`;
    link.textContent = `${c.document_title || "PDF"} ${pageLabel}`;
    container.appendChild(link);
  });
}

function renderExcelCitations(container, citations) {
  (citations || []).forEach((c) => {
    const badge = document.createElement("span");
    badge.className = "citation-badge xlsx-citation-badge";
    if (c.exists === true) badge.classList.add("xlsx-citation-verified");
    else if (c.exists === false) badge.classList.add("citation-badge-unresolved", "xlsx-citation-unverified");
    const suffix = c.exists === true ? " ✓" : c.exists === false ? " ✗" : " ?";
    badge.textContent = `${c.workbook_label}!${c.sheet}!${c.ref} [${c.kind}]${suffix}`;
    container.appendChild(badge);
  });
}

function evidenceParagraph(labelText, valueText) {
  const p = document.createElement("p");
  const label = document.createElement("span");
  label.className = "ws-detail-label";
  label.textContent = labelText;
  p.appendChild(label);
  const br = document.createElement("br");
  p.appendChild(br);
  p.appendChild(document.createTextNode(valueText || "—"));
  return p;
}

function buildDetailContent(finding) {
  const wrap = document.createElement("div");
  wrap.className = "ws-finding-detail-content";

  if (finding.is_duplicate) {
    const note = document.createElement("p");
    note.className = "ws-duplicate-note";
    note.textContent = `Marked as a duplicate of ${finding.duplicate_of} by ${finding.duplicate_marked_by || "—"} at ${formatDate(finding.duplicate_marked_at)}.`;
    wrap.appendChild(note);
  }
  if (finding.duplicate_finding_ids && finding.duplicate_finding_ids.length > 0) {
    const note = document.createElement("p");
    note.className = "ws-duplicate-note";
    note.textContent = `Canonical for duplicate(s): ${finding.duplicate_finding_ids.join(", ")}.`;
    wrap.appendChild(note);
  }

  wrap.appendChild(evidenceParagraph("Explanation", finding.explanation));

  if (finding.origin === "ai") {
    const pdfP = evidenceParagraph("PDF evidence", finding.pdf_evidence);
    wrap.appendChild(pdfP);
    const pdfCiteWrap = document.createElement("div");
    pdfCiteWrap.className = "citation-list";
    renderPdfCitations(pdfCiteWrap, finding.pdf_citations);
    wrap.appendChild(pdfCiteWrap);

    const wbP = evidenceParagraph("Workbook evidence", finding.workbook_evidence);
    wrap.appendChild(wbP);
    const wbCiteWrap = document.createElement("div");
    wbCiteWrap.className = "citation-list";
    renderExcelCitations(wbCiteWrap, finding.excel_citations);
    wrap.appendChild(wbCiteWrap);
  } else {
    wrap.appendChild(evidenceParagraph("Evidence notes", finding.evidence_notes));
    const docsP = document.createElement("p");
    const label = document.createElement("span");
    label.className = "ws-detail-label";
    label.textContent = "Linked documents";
    docsP.appendChild(label);
    docsP.appendChild(document.createElement("br"));
    if ((finding.evidence_document_ids || []).length === 0) {
      docsP.appendChild(document.createTextNode("—"));
    } else {
      finding.evidence_document_ids.forEach((docId, i) => {
        const doc = documentsById.get(docId);
        const link = document.createElement("a");
        link.className = "citation-badge";
        link.target = "_blank";
        link.rel = "noopener";
        link.href = `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(docId)}/download?inline=1`;
        link.textContent = doc ? doc.original_filename : docId;
        docsP.appendChild(link);
        if (i < finding.evidence_document_ids.length - 1) docsP.appendChild(document.createTextNode(" "));
      });
    }
    wrap.appendChild(docsP);
  }

  wrap.appendChild(evidenceParagraph("Commercial / financial relevance", finding.commercial_relevance));
  wrap.appendChild(evidenceParagraph("Uncertainty", finding.uncertainty));
  wrap.appendChild(evidenceParagraph("Recommended action", finding.recommended_action));

  return wrap;
}

function buildWorkflowForm(finding) {
  const wrap = document.createElement("div");
  wrap.className = "ws-finding-detail-workflow";

  const values = editValuesByFindingId.get(finding.id) || {
    review_status: finding.review_status,
    adjusted_severity: finding.adjusted_severity || "",
    resolution_status: finding.resolution_status,
    assigned_owner: finding.assigned_owner,
    management_response: finding.management_response,
    reviewer_notes: finding.reviewer_notes,
    due_date_text: finding.due_date_text,
  };
  editValuesByFindingId.set(finding.id, values);

  const originBadge = document.createElement("span");
  originBadge.className = `ws-badge ws-badge-origin-${finding.origin}`;
  originBadge.textContent = finding.origin === "ai" ? "AI-generated" : "Human-added";
  wrap.appendChild(originBadge);

  function selectField(labelText, id, value, options, onChange) {
    const field = document.createElement("div");
    field.className = "field";
    const label = document.createElement("label");
    label.htmlFor = id;
    label.textContent = labelText;
    field.appendChild(label);
    const select = document.createElement("select");
    select.id = id;
    fillSelect(select, options);
    select.value = value;
    select.addEventListener("change", () => onChange(select.value));
    field.appendChild(select);
    return field;
  }

  function textField(labelText, id, value, multiline, onChange) {
    const field = document.createElement("div");
    field.className = "field";
    const label = document.createElement("label");
    label.htmlFor = id;
    label.textContent = labelText;
    field.appendChild(label);
    const input = document.createElement(multiline ? "textarea" : "input");
    if (!multiline) input.type = "text";
    else input.rows = 2;
    input.id = id;
    input.value = value || "";
    input.addEventListener("input", () => onChange(input.value));
    field.appendChild(input);
    return field;
  }

  wrap.appendChild(
    selectField(
      "Human review status",
      `rf-review-${finding.id}`,
      values.review_status,
      REVIEW_STATUSES.map((s) => [s, REVIEW_STATUS_LABELS[s]]),
      (v) => (values.review_status = v)
    )
  );
  wrap.appendChild(
    selectField(
      "Human-adjusted severity",
      `rf-severity-${finding.id}`,
      values.adjusted_severity,
      [["", `Not adjusted (AI: ${SEVERITY_LABELS[(finding.severity || "unspecified").toLowerCase()] || finding.severity})`], ...SEVERITIES.map((s) => [s, SEVERITY_LABELS[s]])],
      (v) => (values.adjusted_severity = v)
    )
  );
  wrap.appendChild(
    selectField(
      "Resolution status",
      `rf-resolution-${finding.id}`,
      values.resolution_status,
      RESOLUTION_STATUSES.map((s) => [s, RESOLUTION_STATUS_LABELS[s]]),
      (v) => (values.resolution_status = v)
    )
  );
  wrap.appendChild(textField("Assigned owner", `rf-owner-${finding.id}`, values.assigned_owner, false, (v) => (values.assigned_owner = v)));
  wrap.appendChild(textField("Due date", `rf-due-${finding.id}`, values.due_date_text, false, (v) => (values.due_date_text = v)));
  wrap.appendChild(textField("Management response", `rf-response-${finding.id}`, values.management_response, true, (v) => (values.management_response = v)));
  wrap.appendChild(textField("Reviewer notes", `rf-notes-${finding.id}`, values.reviewer_notes, true, (v) => (values.reviewer_notes = v)));

  const saveHint = document.createElement("div");
  saveHint.className = "ws-save-hint";

  const actions = document.createElement("div");
  actions.className = "ws-finding-detail-actions";

  const saveButton = document.createElement("button");
  saveButton.type = "button";
  saveButton.textContent = "Save";
  saveButton.addEventListener("click", async () => {
    saveButton.disabled = true;
    try {
      const res = await fetch(`${apiBase()}/findings/${encodeURIComponent(finding.id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...values, adjusted_severity: values.adjusted_severity || null }),
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        saveHint.textContent = (payload && payload.error) || "Could not save.";
        saveHint.style.color = "var(--danger)";
        return;
      }
      saveHint.textContent = `Saved at ${formatDate(payload.updated_at)}.`;
      saveHint.style.color = "var(--success)";
      await loadWorkspace();
      renderSummary();
      populateFilterOptions();
      renderFindings();
    } finally {
      saveButton.disabled = false;
    }
  });
  actions.appendChild(saveButton);

  const duplicateButton = document.createElement("button");
  duplicateButton.type = "button";
  duplicateButton.className = "button-secondary";
  duplicateButton.textContent = finding.is_duplicate ? "Edit duplicate marking" : "Mark as duplicate";
  duplicateButton.addEventListener("click", () => openDuplicateDialog(finding));
  actions.appendChild(duplicateButton);

  const requestButton = document.createElement("button");
  requestButton.type = "button";
  requestButton.className = "button-secondary";
  requestButton.textContent = "Convert to request";
  requestButton.disabled = !(finding.review_status === "accepted" || finding.review_status === "partially_accepted");
  requestButton.title = requestButton.disabled
    ? "Only accepted or partially accepted findings can be converted to a request"
    : "";
  requestButton.addEventListener("click", () => openRequestDialog(null, finding));
  actions.appendChild(requestButton);

  if (finding.origin === "human") {
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button-danger";
    deleteButton.textContent = "Remove";
    deleteButton.addEventListener("click", () => openDeleteFindingDialog(finding));
    actions.appendChild(deleteButton);
  }

  wrap.appendChild(actions);
  wrap.appendChild(saveHint);
  return wrap;
}

function renderFindings() {
  const tbody = document.getElementById("findings-tbody");
  const list = visibleFindings();
  document.getElementById("findings-count-hint").textContent =
    `Showing ${list.length} of ${report.summary.total_findings} finding(s)` +
    (filters.showDuplicates ? "" : ` (${report.summary.duplicate_count} duplicate(s) hidden)`);
  document.getElementById("findings-empty").hidden = list.length !== 0;
  document.getElementById("findings-table-card").hidden = list.length === 0;

  tbody.textContent = "";
  list.forEach((finding) => {
    const row = document.createElement("tr");
    row.className = `ws-finding-row${finding.is_duplicate ? " is-duplicate" : ""}`;
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.setAttribute("aria-expanded", String(expandedFindingId === finding.id));

    const expandTd = document.createElement("td");
    const expandIcon = document.createElement("span");
    expandIcon.className = "ws-expand-icon";
    expandIcon.textContent = "▸";
    expandTd.appendChild(expandIcon);
    row.appendChild(expandTd);

    const sevTd = document.createElement("td");
    sevTd.appendChild(severityBadge(finding.effective_severity));
    row.appendChild(sevTd);

    const titleTd = document.createElement("td");
    titleTd.textContent = finding.title || "(untitled)";
    row.appendChild(titleTd);

    const classTd = document.createElement("td");
    classTd.textContent = finding.classification || "—";
    row.appendChild(classTd);

    const reviewTd = document.createElement("td");
    reviewTd.appendChild(statusBadge(REVIEW_STATUS_LABELS[finding.review_status] || finding.review_status));
    row.appendChild(reviewTd);

    const resolutionTd = document.createElement("td");
    resolutionTd.appendChild(statusBadge(RESOLUTION_STATUS_LABELS[finding.resolution_status] || finding.resolution_status));
    row.appendChild(resolutionTd);

    const ownerTd = document.createElement("td");
    ownerTd.textContent = finding.assigned_owner || "—";
    row.appendChild(ownerTd);

    const originTd = document.createElement("td");
    originTd.textContent = finding.origin === "ai" ? "AI" : "Human";
    row.appendChild(originTd);

    const toggle = () => {
      expandedFindingId = expandedFindingId === finding.id ? null : finding.id;
      renderFindings();
    };
    row.addEventListener("click", toggle);
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggle();
      }
    });

    tbody.appendChild(row);

    if (expandedFindingId === finding.id) {
      const detailRow = document.createElement("tr");
      detailRow.className = "ws-finding-detail-row";
      const detailTd = document.createElement("td");
      detailTd.colSpan = 8;
      const detail = document.createElement("div");
      detail.className = "ws-finding-detail";
      detail.appendChild(buildDetailContent(finding));
      detail.appendChild(buildWorkflowForm(finding));
      detailTd.appendChild(detail);
      detailRow.appendChild(detailTd);
      tbody.appendChild(detailRow);
    }
  });
}

// -- sorting and filter wiring ------------------------------------------

document.querySelectorAll(".ws-findings-table th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (sortState.key === key) {
      sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
    } else {
      sortState.key = key;
      sortState.dir = "asc";
    }
    document.querySelectorAll(".ws-findings-table th[data-sort]").forEach((h) => h.classList.remove("sorted", "sort-desc"));
    th.classList.add("sorted");
    if (sortState.dir === "desc") th.classList.add("sort-desc");
    renderFindings();
  });
});

function wireFilterInput(id, key, isCheckbox) {
  document.getElementById(id).addEventListener(isCheckbox ? "change" : "input", (e) => {
    filters[key] = isCheckbox ? e.target.checked : e.target.value;
    renderFindings();
  });
}
wireFilterInput("filter-search", "search");
wireFilterInput("filter-severity", "severity");
wireFilterInput("filter-classification", "classification");
wireFilterInput("filter-review-status", "reviewStatus");
wireFilterInput("filter-resolution-status", "resolutionStatus");
wireFilterInput("filter-source-document", "sourceDocument");
wireFilterInput("filter-owner", "owner");
wireFilterInput("filter-show-duplicates", "showDuplicates", true);

document.getElementById("reset-filters").addEventListener("click", () => {
  filters.search = "";
  filters.severity = "all";
  filters.classification = "all";
  filters.reviewStatus = "all";
  filters.resolutionStatus = "all";
  filters.sourceDocument = "all";
  filters.owner = "all";
  filters.showDuplicates = false;
  populateFilterOptions();
  renderFindings();
});

// -- tabs -------------------------------------------------------------

const tabs = [
  ["tab-findings", "panel-findings"],
  ["tab-requests", "panel-requests"],
  ["tab-memo", "panel-memo"],
];
tabs.forEach(([tabId, panelId]) => {
  document.getElementById(tabId).addEventListener("click", () => {
    tabs.forEach(([t, p]) => {
      document.getElementById(t).setAttribute("aria-selected", String(t === tabId));
      document.getElementById(p).hidden = t !== tabId;
    });
  });
});

// -- add finding dialog -----------------------------------------------

const addFindingDialogEl = document.getElementById("add-finding-dialog");
const addFindingFormEl = document.getElementById("add-finding-form");
const addFindingErrorEl = document.getElementById("add-finding-error");

function closeOnBackdropClick(dialog) {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
}
closeOnBackdropClick(addFindingDialogEl);
closeOnBackdropClick(document.getElementById("delete-finding-dialog"));
closeOnBackdropClick(document.getElementById("duplicate-dialog"));
closeOnBackdropClick(document.getElementById("request-dialog"));
closeOnBackdropClick(document.getElementById("approve-memo-dialog"));

document.getElementById("add-finding-button").addEventListener("click", () => {
  addFindingFormEl.reset();
  addFindingErrorEl.textContent = "";
  fillSelect(document.getElementById("hf-severity"), SEVERITIES.map((s) => [s, SEVERITY_LABELS[s]]), { includeBlank: false });
  document.getElementById("hf-severity").value = "";
  const docsSelect = document.getElementById("hf-evidence-documents");
  fillSelect(docsSelect, Array.from(documentsById.values()).map((d) => [d.id, d.original_filename]));
  addFindingDialogEl.showModal();
});
document.getElementById("cancel-add-finding").addEventListener("click", () => addFindingDialogEl.close());

addFindingFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const confirmButton = document.getElementById("confirm-add-finding");
  confirmButton.disabled = true;
  addFindingErrorEl.textContent = "";
  try {
    const evidenceDocs = Array.from(document.getElementById("hf-evidence-documents").selectedOptions).map((o) => o.value);
    const res = await fetch(`${apiBase()}/findings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: document.getElementById("hf-title").value,
        classification: document.getElementById("hf-classification").value,
        severity: document.getElementById("hf-severity").value || null,
        explanation: document.getElementById("hf-explanation").value,
        commercial_relevance: document.getElementById("hf-commercial-relevance").value,
        uncertainty: document.getElementById("hf-uncertainty").value,
        recommended_action: document.getElementById("hf-recommended-action").value,
        evidence_notes: document.getElementById("hf-evidence-notes").value,
        evidence_document_ids: evidenceDocs,
      }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      addFindingErrorEl.textContent = (payload && payload.error) || "Could not add this finding.";
      return;
    }
    addFindingDialogEl.close();
    await loadWorkspace();
    renderSummary();
    populateFilterOptions();
    renderFindings();
  } finally {
    confirmButton.disabled = false;
  }
});

// -- delete finding dialog ------------------------------------------------

const deleteFindingDialogEl = document.getElementById("delete-finding-dialog");
const deleteFindingFormEl = document.getElementById("delete-finding-form");
const deleteFindingErrorEl = document.getElementById("delete-finding-error");
let findingPendingDelete = null;

function openDeleteFindingDialog(finding) {
  findingPendingDelete = finding;
  deleteFindingErrorEl.textContent = "";
  deleteFindingDialogEl.showModal();
}
document.getElementById("cancel-delete-finding").addEventListener("click", () => deleteFindingDialogEl.close());

deleteFindingFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!findingPendingDelete) return;
  const confirmButton = document.getElementById("confirm-delete-finding");
  confirmButton.disabled = true;
  try {
    const res = await fetch(`${apiBase()}/findings/${encodeURIComponent(findingPendingDelete.id)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      deleteFindingErrorEl.textContent = (payload && payload.error) || "Could not remove this finding.";
      return;
    }
    deleteFindingDialogEl.close();
    expandedFindingId = null;
    await loadWorkspace();
    renderSummary();
    populateFilterOptions();
    renderFindings();
  } finally {
    confirmButton.disabled = false;
  }
});

// -- duplicate dialog -----------------------------------------------------

const duplicateDialogEl = document.getElementById("duplicate-dialog");
const duplicateFormEl = document.getElementById("duplicate-form");
const duplicateErrorEl = document.getElementById("duplicate-error");
let findingPendingDuplicate = null;

function openDuplicateDialog(finding) {
  findingPendingDuplicate = finding;
  duplicateErrorEl.textContent = "";
  const select = document.getElementById("duplicate-of-select");
  const others = report.findings.filter((f) => f.id !== finding.id && !(f.is_duplicate && f.duplicate_of));
  fillSelect(select, [
    ["", "— Not a duplicate —"],
    ...others.map((f) => [f.id, `${f.title || "(untitled)"} (${f.id})`]),
  ]);
  select.value = finding.duplicate_of || "";
  document.getElementById("duplicate-marked-by").value = finding.duplicate_marked_by || "";
  duplicateDialogEl.showModal();
}
document.getElementById("cancel-duplicate").addEventListener("click", () => duplicateDialogEl.close());

duplicateFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!findingPendingDuplicate) return;
  const duplicateOf = document.getElementById("duplicate-of-select").value || null;
  const markedBy = document.getElementById("duplicate-marked-by").value.trim();
  if (duplicateOf && !markedBy) {
    duplicateErrorEl.textContent = "Enter your name to record who marked this relationship.";
    return;
  }
  const confirmButton = document.getElementById("confirm-duplicate");
  confirmButton.disabled = true;
  try {
    const res = await fetch(`${apiBase()}/findings/${encodeURIComponent(findingPendingDuplicate.id)}/duplicate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duplicate_of: duplicateOf, marked_by: markedBy }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      duplicateErrorEl.textContent = (payload && payload.error) || "Could not save this relationship.";
      return;
    }
    duplicateDialogEl.close();
    await loadWorkspace();
    renderSummary();
    populateFilterOptions();
    renderFindings();
  } finally {
    confirmButton.disabled = false;
  }
});

// -- information requests --------------------------------------------------

function requestCard(request) {
  const card = document.createElement("div");
  card.className = "ws-request-card";

  const question = document.createElement("p");
  question.className = "ws-request-question";
  question.textContent = request.question;
  card.appendChild(question);

  const meta = document.createElement("div");
  meta.className = "ws-request-meta";
  const headerStatusBadge = statusBadge(REQUEST_STATUS_LABELS[request.status] || request.status);
  meta.appendChild(headerStatusBadge);
  const priority = document.createElement("span");
  priority.className = "ws-badge";
  priority.textContent = `Priority: ${request.priority}`;
  meta.appendChild(priority);
  if (request.related_finding_ids.length > 0) {
    const related = document.createElement("span");
    related.className = "ws-badge";
    related.textContent = `Related: ${request.related_finding_ids.join(", ")}`;
    meta.appendChild(related);
  }
  card.appendChild(meta);

  const fields = document.createElement("div");
  fields.className = "ws-request-fields";

  const statusField = document.createElement("div");
  statusField.className = "field";
  const statusLabel = document.createElement("label");
  statusLabel.textContent = "Status";
  statusField.appendChild(statusLabel);
  const statusSelect = document.createElement("select");
  fillSelect(statusSelect, REQUEST_STATUSES.map((s) => [s, REQUEST_STATUS_LABELS[s]]));
  statusSelect.value = request.status;
  statusField.appendChild(statusSelect);
  fields.appendChild(statusField);

  const recipientField = document.createElement("div");
  recipientField.className = "field";
  const recipientLabel = document.createElement("label");
  recipientLabel.textContent = "Assigned recipient";
  recipientField.appendChild(recipientLabel);
  const recipientInput = document.createElement("input");
  recipientInput.type = "text";
  recipientInput.value = request.assigned_recipient;
  recipientField.appendChild(recipientInput);
  fields.appendChild(recipientField);

  const responseField = document.createElement("div");
  responseField.className = "field";
  const responseLabel = document.createElement("label");
  responseLabel.textContent = "Management response";
  responseField.appendChild(responseLabel);
  const responseTextarea = document.createElement("textarea");
  responseTextarea.rows = 2;
  responseTextarea.value = request.management_response;
  responseField.appendChild(responseTextarea);
  fields.appendChild(responseField);

  const followupField = document.createElement("div");
  followupField.className = "field";
  const followupLabel = document.createElement("label");
  followupLabel.textContent = "Reviewer follow-up";
  followupField.appendChild(followupLabel);
  const followupTextarea = document.createElement("textarea");
  followupTextarea.rows = 2;
  followupTextarea.value = request.reviewer_followup;
  followupField.appendChild(followupTextarea);
  fields.appendChild(followupField);

  card.appendChild(fields);

  const saveHint = document.createElement("div");
  saveHint.className = "ws-save-hint";

  const saveButton = document.createElement("button");
  saveButton.type = "button";
  saveButton.style.marginTop = "10px";
  saveButton.textContent = "Save request";
  saveButton.addEventListener("click", async () => {
    saveButton.disabled = true;
    try {
      const res = await fetch(`${apiBase()}/requests/${encodeURIComponent(request.id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: statusSelect.value,
          assigned_recipient: recipientInput.value,
          management_response: responseTextarea.value,
          reviewer_followup: followupTextarea.value,
        }),
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        saveHint.textContent = (payload && payload.error) || "Could not save.";
        saveHint.style.color = "var(--danger)";
        return;
      }
      saveHint.textContent = `Saved at ${formatDate(payload.updated_at)}.`;
      saveHint.style.color = "var(--success)";
      headerStatusBadge.textContent = REQUEST_STATUS_LABELS[payload.status] || payload.status;
      await Promise.all([loadRequests(), loadWorkspace()]);
      renderSummary();
    } finally {
      saveButton.disabled = false;
    }
  });
  card.appendChild(saveButton);
  card.appendChild(saveHint);

  return card;
}

function renderRequests() {
  const list = document.getElementById("requests-list");
  list.textContent = "";
  document.getElementById("requests-empty").hidden = requestsState.length !== 0;
  requestsState.forEach((r) => list.appendChild(requestCard(r)));
}

const requestDialogEl = document.getElementById("request-dialog");
const requestFormEl = document.getElementById("request-form");
const requestErrorEl = document.getElementById("request-error");

function openRequestDialog(existing, prefillFinding) {
  requestFormEl.reset();
  requestErrorEl.textContent = "";
  document.getElementById("request-dialog-title").textContent = "New information request";
  fillSelect(document.getElementById("req-priority"), REQUEST_PRIORITIES.map((p) => [p, p[0].toUpperCase() + p.slice(1)]));
  document.getElementById("req-priority").value = "medium";
  const relatedSelect = document.getElementById("req-related-findings");
  fillSelect(
    relatedSelect,
    report.findings.map((f) => [f.id, `${f.title || "(untitled)"} (${f.id})`])
  );
  if (prefillFinding) {
    document.getElementById("req-question").value = `Regarding "${prefillFinding.title}": `;
    Array.from(relatedSelect.options).forEach((o) => {
      if (o.value === prefillFinding.id) o.selected = true;
    });
  }
  requestDialogEl.showModal();
}
document.getElementById("add-request-button").addEventListener("click", () => openRequestDialog(null, null));
document.getElementById("cancel-request").addEventListener("click", () => requestDialogEl.close());

requestFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const confirmButton = document.getElementById("confirm-request");
  confirmButton.disabled = true;
  requestErrorEl.textContent = "";
  try {
    const related = Array.from(document.getElementById("req-related-findings").selectedOptions).map((o) => o.value);
    const res = await fetch(`${apiBase()}/requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: document.getElementById("req-question").value,
        priority: document.getElementById("req-priority").value,
        assigned_recipient: document.getElementById("req-recipient").value,
        related_finding_ids: related,
      }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      requestErrorEl.textContent = (payload && payload.error) || "Could not create this request.";
      return;
    }
    requestDialogEl.close();
    await Promise.all([loadRequests(), loadWorkspace()]);
    renderRequests();
    renderSummary();
  } finally {
    confirmButton.disabled = false;
  }
});

// -- memo -------------------------------------------------------------

const MEMO_FIELD_IDS = {
  executive_conclusion: "memo-executive-conclusion",
  transaction_overview: "memo-transaction-overview",
  critical_issues: "memo-critical-issues",
  high_priority_issues: "memo-high-priority-issues",
  financial_valuation_implications: "memo-financial-implications",
  missing_information: "memo-missing-information",
  confirmed_consistencies: "memo-confirmed-consistencies",
  recommended_next_actions: "memo-next-actions",
};

function renderMemo() {
  if (!memoState) return;
  fillSelect(document.getElementById("memo-recommendation"), MEMO_RECOMMENDATIONS.map((r) => [r, MEMO_RECOMMENDATION_LABELS[r]]));
  document.getElementById("memo-recommendation").value = memoState.overall_recommendation;

  Object.entries(MEMO_FIELD_IDS).forEach(([field, id]) => {
    document.getElementById(id).value = memoState[field] || "";
  });

  const badge = document.getElementById("memo-status-badge");
  badge.textContent = memoState.status === "approved" ? "Approved" : "Draft";
  badge.className = `ws-badge ${memoState.status === "approved" ? "ws-badge-approved" : "ws-badge-draft"}`;

  const note = document.getElementById("memo-approval-note");
  note.textContent =
    memoState.status === "approved"
      ? `Approved by ${memoState.approved_by} at ${formatDate(memoState.approved_at)}.`
      : "Not yet approved.";

  document.getElementById("approve-memo-button").disabled = memoState.status === "approved";
}

document.getElementById("save-memo-button").addEventListener("click", async () => {
  const errorEl = document.getElementById("memo-error");
  const statusEl = document.getElementById("memo-save-status");
  errorEl.textContent = "";
  const body = { overall_recommendation: document.getElementById("memo-recommendation").value };
  Object.entries(MEMO_FIELD_IDS).forEach(([field, id]) => {
    body[field] = document.getElementById(id).value;
  });
  const res = await fetch(`${apiBase()}/memo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    errorEl.textContent = (payload && payload.error) || "Could not save the memo.";
    return;
  }
  memoState = payload;
  renderMemo();
  statusEl.textContent = `Saved at ${formatDate(payload.updated_at)}.`;
});

const approveMemoDialogEl = document.getElementById("approve-memo-dialog");
const approveMemoFormEl = document.getElementById("approve-memo-form");
const approveMemoErrorEl = document.getElementById("approve-memo-error");

document.getElementById("approve-memo-button").addEventListener("click", () => {
  approveMemoFormEl.reset();
  approveMemoErrorEl.textContent = "";
  approveMemoDialogEl.showModal();
});
document.getElementById("cancel-approve-memo").addEventListener("click", () => approveMemoDialogEl.close());

approveMemoFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const confirmButton = document.getElementById("confirm-approve-memo");
  confirmButton.disabled = true;
  try {
    const res = await fetch(`${apiBase()}/memo/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true, approver: document.getElementById("approve-memo-name").value }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      approveMemoErrorEl.textContent = (payload && payload.error) || "Could not approve the memo.";
      return;
    }
    memoState = payload;
    renderMemo();
    approveMemoDialogEl.close();
  } finally {
    confirmButton.disabled = false;
  }
});

// -- exports -------------------------------------------------------------

function wireExportLinks() {
  document.getElementById("export-findings-link").href = `${apiBase()}/export/findings.xlsx`;
  document.getElementById("export-requests-link").href = `${apiBase()}/export/requests.xlsx`;
  document.getElementById("export-package-link").href = `${apiBase()}/export/package.html`;
}

// -- boot -------------------------------------------------------------

async function init() {
  if (!projectId || !workspaceId) {
    loadingCardEl.hidden = true;
    errorCardEl.hidden = false;
    errorTextEl.textContent = "Missing project or workspace reference.";
    return;
  }
  try {
    const projectRes = await fetch(`/api/projects/${encodeURIComponent(projectId)}`);
    const projectName = projectRes.ok ? (await projectRes.json()).name : "Project";
    setBreadcrumb(projectName);

    await Promise.all([loadWorkspace(), loadDocuments(), loadRequests(), loadMemo()]);
    report.__projectName = projectName;

    loadingCardEl.hidden = true;
    contentEl.hidden = false;

    renderSummary();
    populateFilterOptions();
    renderFindings();
    renderRequests();
    renderMemo();
    wireExportLinks();
  } catch (err) {
    loadingCardEl.hidden = true;
    errorCardEl.hidden = false;
    errorTextEl.textContent = err.message || "Could not load this workspace.";
  }
}

init();
