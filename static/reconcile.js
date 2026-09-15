// Cross-format reconciliation results page: shows one PDF+Excel
// reconciliation record. PDF evidence uses Anthropic's native citations
// (page_location, resolved server-side to a document id); Excel evidence
// uses this app's own citation convention (resolved server-side to a
// document id via a stable "Workbook N" label, then mechanically verified
// against the real workbook's structure). Both kinds arrive already parsed
// and resolved from the server - this page only renders what it's given
// and never re-derives or guesses a reference.

const metaEl = document.getElementById("reconcile-meta");
const errorCardEl = document.getElementById("reconcile-error-card");
const errorTextEl = document.getElementById("reconcile-error-text");
const verificationCardEl = document.getElementById("reconcile-verification-card");
const verificationNoteEl = document.getElementById("reconcile-verification-note");
const resultsCardEl = document.getElementById("reconcile-results-card");
const segmentsEl = document.getElementById("reconcile-segments");
const traceCardEl = document.getElementById("reconcile-trace-card");
const traceListEl = document.getElementById("reconcile-trace-list");
const breadcrumbEl = document.getElementById("app-breadcrumb");
const workspaceActionCardEl = document.getElementById("workspace-action-card");
const openWorkspaceButtonEl = document.getElementById("open-workspace-button");
const workspaceActionErrorEl = document.getElementById("workspace-action-error");

const params = new URLSearchParams(window.location.search);
const projectId = params.get("project");
const analysisId = params.get("analysis");

const ERROR_LABELS = {
  missing_api_key: "No Anthropic API key is configured.",
  invalid_api_key: "The configured Anthropic API key was rejected.",
  insufficient_credit: "The Anthropic account has insufficient credit.",
  rate_limit: "Anthropic's rate limit was reached.",
  network_error: "Could not reach the Anthropic API.",
  model_unavailable: "The configured Claude model is not available.",
  missing_file: "A stored file for one of the selected documents is missing on disk.",
  no_documents: "No documents were selected.",
  unsupported_type: "Only PDF and Excel documents can be included in a reconciliation.",
  missing_pdf: "At least one PDF document is required.",
  missing_excel: "At least one Excel workbook is required.",
  too_many_pdf_documents: "Too many PDFs were selected for one run.",
  too_many_excel_documents: "Too many Excel workbooks were selected for one run.",
  oversized_pdf_total: "The selected PDFs are too large to send in one request.",
  oversized_excel_workbook: "One of the selected workbooks is too large to upload.",
  encrypted_pdf: "One of the selected PDFs is password-protected or encrypted.",
  malformed_pdf: "One of the selected PDFs could not be read.",
  invalid_pdf: "Claude could not process one of the selected PDFs.",
  upload_failed: "Uploading a workbook to Anthropic failed.",
  still_paused: "Claude's analysis paused repeatedly and did not finish in time.",
  refused: "Claude declined to analyze these documents.",
  truncated_response: "Claude's analysis was cut off before finishing.",
  empty_response: "Claude returned no analysis text.",
  unexpected_error: "The reconciliation failed unexpectedly.",
};

const VERIFICATION_UNAVAILABLE_LABELS = {
  encrypted_workbook: "appears to be password-protected, so its references could not be checked locally.",
  malformed_workbook: "could not be opened locally, so its references could not be checked.",
  unsupported_extension: "isn't a supported file type for local reference verification.",
  not_attempted: "verification was not attempted because the analysis did not complete.",
};

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
  current.textContent = "Cross-format reconciliation";

  breadcrumbEl.append(homeLink, sep1, projectLink, sep2, current);
}

function pdfViewUrl(documentId, page) {
  const base = `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}/download?inline=1`;
  return page ? `${base}#page=${page}` : base;
}

function downloadUrl(documentId) {
  return `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}/download`;
}

function renderMeta(record) {
  metaEl.textContent = "";
  metaEl.className = "card inspection-meta";

  const title = document.createElement("div");
  title.className = "name";
  title.textContent = `Cross-format reconciliation (${record.pdf_document_filenames.length} PDF, ${record.excel_document_filenames.length} Excel)`;
  metaEl.appendChild(title);

  const sourcesLabel = document.createElement("div");
  sourcesLabel.className = "section-label";
  sourcesLabel.textContent = "PDF sources";
  metaEl.appendChild(sourcesLabel);

  const pdfList = document.createElement("ul");
  pdfList.className = "cross-confirm-list";
  record.pdf_document_filenames.forEach((filename, index) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = pdfViewUrl(record.pdf_document_ids[index]);
    link.target = "_blank";
    link.rel = "noopener";
    link.className = "link-action";
    link.textContent = filename;
    link.title = `SHA-256: ${record.pdf_document_checksums[index]}`;
    item.appendChild(link);
    pdfList.appendChild(item);
  });
  metaEl.appendChild(pdfList);

  const excelLabel = document.createElement("div");
  excelLabel.className = "section-label";
  excelLabel.textContent = "Excel sources";
  metaEl.appendChild(excelLabel);

  const excelList = document.createElement("ul");
  excelList.className = "cross-confirm-list";
  const cleanupByDocId = new Map((record.excel_cleanup || []).map((c) => [c.document_id, c]));
  record.excel_document_filenames.forEach((filename, index) => {
    const documentId = record.excel_document_ids[index];
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = downloadUrl(documentId);
    link.className = "link-action";
    link.textContent = filename;
    link.title = `SHA-256: ${record.excel_document_checksums[index]}`;
    item.appendChild(link);

    const cleanup = cleanupByDocId.get(documentId);
    const status = document.createElement("span");
    status.className = "muted";
    if (!cleanup || !cleanup.attempted) {
      status.textContent = " — deletion from Anthropic not attempted";
    } else if (cleanup.succeeded) {
      status.textContent = " — deleted from Anthropic afterward";
    } else {
      status.textContent = " — deletion from Anthropic failed";
    }
    item.appendChild(status);
    excelList.appendChild(item);
  });
  metaEl.appendChild(excelList);

  const list = document.createElement("dl");
  list.className = "inspection-facts";

  const facts = [
    ["Model", record.model],
    ["Mandate version", record.mandate_version],
    ["Sent to Anthropic", record.transmitted ? "Yes" : "No"],
    [
      "Tokens used",
      record.input_tokens != null ? `${record.input_tokens} in / ${record.output_tokens} out` : "—",
    ],
    ["Code execution calls", record.code_execution_requests != null ? String(record.code_execution_requests) : "—"],
    ["Stop reason", record.stop_reason || "—"],
    ["Analysis time", `${record.analysis_seconds.toFixed(1)}s`],
    ["Run at", formatDate(record.created_at)],
  ];

  for (const [label, value] of facts) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    list.append(dt, dd);
  }

  metaEl.appendChild(list);

  if (record.excel_cleanup && record.excel_cleanup.length > 0) {
    const note = document.createElement("p");
    note.className = "xlsx-retention-note";
    note.textContent =
      "Deleting Anthropic's Files API copy of each workbook stops future access through that API, but " +
      "does not by itself guarantee the workbook is immediately erased from an in-progress request or " +
      "from Anthropic's code-execution container, which is retained separately for up to 30 days.";
    metaEl.appendChild(note);
  }
}

function renderVerificationNote(record) {
  const unavailable = (record.excel_verification || []).filter((v) => !v.available);
  if (unavailable.length === 0) return;
  verificationCardEl.hidden = false;
  const filenameByDocId = new Map(
    record.excel_document_ids.map((id, i) => [id, record.excel_document_filenames[i]])
  );
  const notes = unavailable.map((v) => {
    const filename = filenameByDocId.get(v.document_id) || "a workbook";
    const reason = VERIFICATION_UNAVAILABLE_LABELS[v.unavailable_reason] || "its references could not be checked.";
    return `"${filename}" ${reason}`;
  });
  verificationNoteEl.textContent = `Citation references below could not be independently verified this run: ${notes.join(" ")}`;
}

const HEADING_RE = /^##\s+(.*)$/;
const LIST_ITEM_RE = /^(?:[-*]|\d+\.)\s+/;
const FIELD_LABEL_RE = /^\*\*[^*]+:\*\*/;

function appendInlineFormatted(container, text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  parts.forEach((part) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      const strong = document.createElement("strong");
      strong.textContent = part.slice(2, -2);
      container.appendChild(strong);
    } else if (part) {
      container.appendChild(document.createTextNode(part));
    }
  });
}

function renderPdfCitations(container, citations) {
  if (!citations || citations.length === 0) return;
  const wrap = document.createElement("span");
  wrap.className = "citation-list";
  citations.forEach((citation) => {
    const link = document.createElement("a");
    link.className = "citation-badge";
    link.target = "_blank";
    link.rel = "noopener";
    if (citation.document_id) {
      link.href = pdfViewUrl(citation.document_id, citation.start_page);
    } else {
      link.removeAttribute("target");
      link.classList.add("citation-badge-unresolved");
    }
    const titleText = citation.document_title || "document";
    link.title = `${titleText} — ${citation.cited_text}`;
    const shortTitle = titleText.length > 22 ? `${titleText.slice(0, 19)}…` : titleText;
    const pageLabel =
      citation.end_page && citation.end_page !== citation.start_page
        ? `p. ${citation.start_page}–${citation.end_page}`
        : `p. ${citation.start_page}`;
    link.textContent = `${shortTitle} ${pageLabel}`;
    wrap.appendChild(link);
  });
  container.appendChild(wrap);
}

function renderExcelCitationBadge(container, citation) {
  const badge = document.createElement("span");
  badge.className = "citation-badge xlsx-citation-badge";
  let statusSuffix = " ?";
  let title = "Could not be verified against the workbook this run.";
  if (citation.document_id === null) {
    badge.classList.add("citation-badge-unresolved", "xlsx-citation-unverified");
    statusSuffix = " ✗";
    title = "This citation's workbook label was not recognized - it could not be resolved to any selected workbook.";
  } else if (citation.exists === true) {
    badge.classList.add("xlsx-citation-verified");
    statusSuffix = " ✓";
    title = `Verified against "${citation.document_filename}": this sheet and cell/range exist in the workbook.`;
  } else if (citation.exists === false) {
    badge.classList.add("citation-badge-unresolved", "xlsx-citation-unverified");
    statusSuffix = " ✗";
    title = `Not found in "${citation.document_filename}" - this reference could not be verified.`;
  } else if (citation.document_filename) {
    title = `Could not be verified against "${citation.document_filename}" this run.`;
  }
  badge.title = title;
  const workbookLabel = citation.document_filename ? citation.workbook_label : `${citation.workbook_label} (unresolved)`;
  badge.textContent = `${workbookLabel}!${citation.sheet}!${citation.ref} [${citation.kind}]${statusSuffix}`;
  container.appendChild(badge);
}

// Reconstructs each content block's full text (parts[].text concatenated,
// with an excel_citation part treated as one opaque, non-splittable piece -
// it never contains a literal newline) into lines, carrying along the
// block's native PDF citations so they can be rendered once per closed
// paragraph/bullet - the same line-reconstruction approach used by
// cross-analysis.js and workbook-inspect.js, combined here since a single
// block can carry both kinds of evidence at once.
function segmentsToLines(segments) {
  const lines = [[]];
  segments.forEach((segment) => {
    const pdfCitations = segment.pdf_citations || [];
    (segment.parts || []).forEach((part) => {
      if (part.type === "excel_citation") {
        lines[lines.length - 1].push({ type: "excel_citation", citation: part.citation, pdfCitations: [] });
        return;
      }
      const chunks = (part.text || "").split("\n");
      chunks.forEach((chunk, index) => {
        if (index > 0) lines.push([]);
        if (chunk) lines[lines.length - 1].push({ type: "text", text: chunk, pdfCitations });
      });
    });
  });
  return lines;
}

function lineText(pieces) {
  return pieces
    .filter((p) => p.type === "text")
    .map((p) => p.text)
    .join("");
}

function renderSegments(record) {
  segmentsEl.textContent = "";
  const lines = segmentsToLines(record.segments);
  let block = null; // { pieces: [], pdfCitations: [] } | null

  const closeBlock = () => {
    if (!block) return;
    const pieces = block.pieces;
    const pdfCitations = block.pdfCitations;
    block = null;
    if (pieces.length === 0) return;

    const firstText = lineText([pieces[0]]).trimStart();
    const isBullet = LIST_ITEM_RE.test(firstText);
    const wrapper = document.createElement(isBullet ? "div" : "p");
    wrapper.className = isBullet ? "inspection-bullet" : "inspection-paragraph";

    const textSpan = document.createElement("span");
    const renderPieces = (list) => {
      list.forEach((piece) => {
        if (piece.type === "excel_citation") {
          renderExcelCitationBadge(textSpan, piece.citation);
        } else {
          appendInlineFormatted(textSpan, piece.text);
        }
      });
    };
    if (isBullet && pieces[0].type === "text") {
      const stripped = pieces[0].text.replace(LIST_ITEM_RE, "");
      renderPieces([{ type: "text", text: stripped }, ...pieces.slice(1)]);
    } else {
      renderPieces(pieces);
    }
    wrapper.appendChild(textSpan);
    renderPdfCitations(wrapper, pdfCitations);
    segmentsEl.appendChild(wrapper);
  };

  lines.forEach((pieces) => {
    const trimmed = lineText(pieces).trim();
    const linePdfCitations = pieces.flatMap((p) => p.pdfCitations || []);
    const headingMatch = HEADING_RE.exec(trimmed);

    if (headingMatch && pieces.every((p) => p.type === "text")) {
      closeBlock();
      const heading = document.createElement("h3");
      heading.className = "inspection-heading";
      heading.textContent = headingMatch[1].trim();
      segmentsEl.appendChild(heading);
      return;
    }

    if (!trimmed && pieces.every((p) => p.type === "text")) {
      closeBlock(); // blank line: paragraph break
      return;
    }

    const startsNewItem = LIST_ITEM_RE.test(trimmed) || FIELD_LABEL_RE.test(trimmed);
    if (startsNewItem || !block) {
      closeBlock();
      block = { pieces: [...pieces], pdfCitations: [...linePdfCitations] };
    } else {
      block.pieces.push({ type: "text", text: " " }, ...pieces);
      block.pdfCitations.push(...linePdfCitations);
    }
  });
  closeBlock();
}

function renderToolTrace(record) {
  if (!record.tool_trace || record.tool_trace.length === 0) return;
  traceCardEl.hidden = false;
  traceListEl.textContent = "";

  record.tool_trace.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "xlsx-trace-entry";

    const kind = document.createElement("div");
    kind.className = "xlsx-trace-kind";
    kind.textContent = entry.kind;
    item.appendChild(kind);

    const detail = document.createElement("pre");
    detail.className = "xlsx-trace-detail";
    if (entry.kind === "tool_use") {
      detail.textContent = `${entry.tool}: ${entry.input}`;
    } else if (entry.kind === "bash_result") {
      detail.textContent = `return_code=${entry.return_code}\nstdout: ${entry.stdout}\nstderr: ${entry.stderr}`;
    } else if (entry.kind === "bash_error") {
      detail.textContent = `error_code=${entry.error_code}`;
    } else {
      detail.textContent = JSON.stringify(entry);
    }
    item.appendChild(detail);

    traceListEl.appendChild(item);
  });
}

function renderError(record) {
  errorCardEl.hidden = false;
  errorTextEl.textContent =
    ERROR_LABELS[record.error_type] || record.error_message || "The analysis did not complete.";

  if (record.error_message && ERROR_LABELS[record.error_type]) {
    const detail = document.createElement("p");
    detail.className = "inspection-error-detail";
    detail.textContent = record.error_message;
    errorCardEl.appendChild(detail);
  }

  // Truncated responses still carry partial analysis worth showing.
  if (record.segments && record.segments.length > 0) {
    resultsCardEl.hidden = false;
    renderVerificationNote(record);
    renderSegments(record);
  }
  renderToolTrace(record);
}

async function loadReconciliation() {
  if (!projectId || !analysisId) {
    metaEl.textContent = "";
    const p = document.createElement("p");
    p.textContent = "Missing project or analysis reference.";
    metaEl.appendChild(p);
    return;
  }

  const [projectRes, analysisRes] = await Promise.all([
    fetch(`/api/projects/${encodeURIComponent(projectId)}`),
    fetch(`/api/projects/${encodeURIComponent(projectId)}/reconciliations/${encodeURIComponent(analysisId)}`),
  ]);

  setBreadcrumb(projectRes.ok ? (await projectRes.json()).name : "Project");

  if (!analysisRes.ok) {
    metaEl.textContent = "";
    const p = document.createElement("p");
    p.textContent = "Reconciliation not found.";
    metaEl.appendChild(p);
    return;
  }

  const record = await analysisRes.json();
  renderMeta(record);

  if (record.status === "success") {
    workspaceActionCardEl.hidden = false;
    resultsCardEl.hidden = false;
    renderVerificationNote(record);
    renderSegments(record);
    renderToolTrace(record);
  } else {
    renderError(record);
  }
}

openWorkspaceButtonEl.addEventListener("click", async () => {
  workspaceActionErrorEl.textContent = "";
  openWorkspaceButtonEl.disabled = true;
  openWorkspaceButtonEl.textContent = "Opening…";
  try {
    const res = await fetch(
      `/api/projects/${encodeURIComponent(projectId)}/cross-format-analyses/${encodeURIComponent(analysisId)}/workspace`,
      { method: "POST" }
    );
    const payload = await res.json().catch(() => null);
    if (!res.ok || !payload || !payload.id) {
      workspaceActionErrorEl.textContent = (payload && payload.error) || "Could not open the deal workspace.";
      return;
    }
    window.location.href = `/workspace.html?project=${encodeURIComponent(projectId)}&workspace=${encodeURIComponent(payload.id)}`;
  } catch (err) {
    workspaceActionErrorEl.textContent = "Could not reach the local app server.";
  } finally {
    openWorkspaceButtonEl.disabled = false;
    openWorkspaceButtonEl.textContent = "Open deal workspace";
  }
});

loadReconciliation();
