// Workbook inspection results page: shows one XLSX/XLS inspection record.
// Unlike PDF citations (a native Anthropic feature), sheet/cell citations
// here are a convention this app defines and parses out of Claude's text
// server-side (see xlsx_inspection.py), then verifies against the real
// workbook's structure. Citation segments arrive already parsed and
// verified from the server - this page only renders what it's given and
// never re-derives or guesses a reference.

const metaEl = document.getElementById("xlsx-meta");
const errorCardEl = document.getElementById("xlsx-error-card");
const errorTextEl = document.getElementById("xlsx-error-text");
const verificationCardEl = document.getElementById("xlsx-verification-card");
const verificationNoteEl = document.getElementById("xlsx-verification-note");
const resultsCardEl = document.getElementById("xlsx-results-card");
const segmentsEl = document.getElementById("xlsx-segments");
const traceCardEl = document.getElementById("xlsx-trace-card");
const traceListEl = document.getElementById("xlsx-trace-list");
const breadcrumbEl = document.getElementById("app-breadcrumb");

const params = new URLSearchParams(window.location.search);
const projectId = params.get("project");
const inspectionId = params.get("inspection");

const ERROR_LABELS = {
  missing_api_key: "No Anthropic API key is configured.",
  invalid_api_key: "The configured Anthropic API key was rejected.",
  insufficient_credit: "The Anthropic account has insufficient credit.",
  rate_limit: "Anthropic's rate limit was reached.",
  network_error: "Could not reach the Anthropic API.",
  model_unavailable: "The configured Claude model is not available.",
  missing_file: "The stored file for this document is missing on disk.",
  oversized_workbook: "This workbook is too large to upload for inspection.",
  not_workbook: "Only .xlsx or .xls documents can be inspected with this action.",
  upload_failed: "Uploading the workbook to Anthropic failed.",
  still_paused: "Claude's analysis paused repeatedly and did not finish in time.",
  refused: "Claude declined to analyze this workbook.",
  truncated_response: "Claude's analysis was cut off before finishing.",
  empty_response: "Claude returned no analysis text.",
  unexpected_error: "The workbook inspection failed unexpectedly.",
};

const VERIFICATION_UNAVAILABLE_LABELS = {
  encrypted_workbook: "the workbook appears to be password-protected, so references could not be checked locally.",
  malformed_workbook: "the workbook could not be opened locally, so references could not be checked.",
  unsupported_extension: "this file type isn't supported for local reference verification.",
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
  current.textContent = "Workbook inspection";

  breadcrumbEl.append(homeLink, sep1, projectLink, sep2, current);
}

function renderMeta(record) {
  metaEl.textContent = "";
  metaEl.className = "card inspection-meta";

  const title = document.createElement("div");
  title.className = "name";
  title.textContent = record.document_filename;
  metaEl.appendChild(title);

  const list = document.createElement("dl");
  list.className = "inspection-facts";

  const cleanupLabel = !record.remote_cleanup_attempted
    ? "Not attempted"
    : record.remote_cleanup_succeeded
      ? "Yes"
      : "Attempted, failed";

  const facts = [
    ["Model", record.model],
    ["Sent to Anthropic", record.transmitted ? "Yes" : "No"],
    ["Deleted from Anthropic afterward", cleanupLabel],
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

  if (record.remote_cleanup_attempted) {
    const note = document.createElement("p");
    note.className = "xlsx-retention-note";
    note.textContent =
      "Deleting Anthropic's Files API copy stops future access through that API, but does not by " +
      "itself guarantee the workbook is immediately erased from an in-progress request or from " +
      "Anthropic's code-execution container, which is retained separately for up to 30 days.";
    metaEl.appendChild(note);
  }
}

function renderVerificationNote(record) {
  if (record.verification_available) return;
  verificationCardEl.hidden = false;
  const reason = VERIFICATION_UNAVAILABLE_LABELS[record.verification_unavailable_reason] || "references could not be checked.";
  verificationNoteEl.textContent = `Citation references below could not be independently verified this run: ${reason}`;
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

function renderCitationBadge(container, citation) {
  const badge = document.createElement("span");
  badge.className = "citation-badge xlsx-citation-badge";
  let statusSuffix = " ?";
  let title = "Could not be verified against the workbook this run.";
  if (citation.exists === true) {
    badge.classList.add("xlsx-citation-verified");
    statusSuffix = " ✓";
    title = "Verified: this sheet and cell/range exist in the workbook.";
  } else if (citation.exists === false) {
    badge.classList.add("citation-badge-unresolved", "xlsx-citation-unverified");
    statusSuffix = " ✗";
    title = "Not found in the workbook - this reference could not be verified.";
  }
  badge.title = title;
  badge.textContent = `${citation.sheet}!${citation.ref} [${citation.kind}]${statusSuffix}`;
  container.appendChild(badge);
}

function renderPieces(container, pieces) {
  pieces.forEach((piece) => {
    if (piece.type === "citation") {
      renderCitationBadge(container, piece.citation);
    } else {
      appendInlineFormatted(container, piece.text);
    }
  });
}

// Mirrors the line-reconstruction approach used for PDF citations
// (inspect.js / cross-analysis.js), adapted for segments that are already
// {type: "text" | "citation"} pairs from the server rather than raw API
// content blocks - headings/bullets/paragraphs are still only findable by
// looking at whole lines, so text segments are split on "\n" here while
// citation segments (which never contain a literal newline) pass through
// as single, indivisible pieces anchored to whichever line they fall on.
function segmentsToLines(segments) {
  const lines = [[]];
  segments.forEach((segment) => {
    if (segment.type === "citation") {
      lines[lines.length - 1].push({ type: "citation", citation: segment.citation });
      return;
    }
    const parts = (segment.text || "").split("\n");
    parts.forEach((part, index) => {
      if (index > 0) lines.push([]);
      if (part) lines[lines.length - 1].push({ type: "text", text: part });
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
  let block = null; // { pieces: [] } | null

  const closeBlock = () => {
    if (!block) return;
    const pieces = block.pieces;
    block = null;
    if (pieces.length === 0) return;

    const firstText = lineText([pieces[0]]).trimStart();
    const isBullet = LIST_ITEM_RE.test(firstText);
    const wrapper = document.createElement(isBullet ? "div" : "p");
    wrapper.className = isBullet ? "inspection-bullet" : "inspection-paragraph";

    const textSpan = document.createElement("span");
    if (isBullet && pieces[0].type === "text") {
      const stripped = pieces[0].text.replace(LIST_ITEM_RE, "");
      renderPieces(textSpan, [{ type: "text", text: stripped }, ...pieces.slice(1)]);
    } else {
      renderPieces(textSpan, pieces);
    }
    wrapper.appendChild(textSpan);
    segmentsEl.appendChild(wrapper);
  };

  lines.forEach((pieces) => {
    const trimmed = lineText(pieces).trim();
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
      block = { pieces: [...pieces] };
    } else {
      // continuation of the open paragraph/bullet: keep a visible space
      // between lines that were joined by a newline in the source text.
      block.pieces.push({ type: "text", text: " " }, ...pieces);
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

async function loadXlsxInspection() {
  if (!projectId || !inspectionId) {
    metaEl.textContent = "";
    const p = document.createElement("p");
    p.textContent = "Missing project or inspection reference.";
    metaEl.appendChild(p);
    return;
  }

  const [projectRes, inspectionRes] = await Promise.all([
    fetch(`/api/projects/${encodeURIComponent(projectId)}`),
    fetch(`/api/projects/${encodeURIComponent(projectId)}/workbook-inspections/${encodeURIComponent(inspectionId)}`),
  ]);

  setBreadcrumb(projectRes.ok ? (await projectRes.json()).name : "Project");

  if (!inspectionRes.ok) {
    metaEl.textContent = "";
    const p = document.createElement("p");
    p.textContent = "Workbook inspection not found.";
    metaEl.appendChild(p);
    return;
  }

  const record = await inspectionRes.json();
  renderMeta(record);

  if (record.status === "success") {
    resultsCardEl.hidden = false;
    renderVerificationNote(record);
    renderSegments(record);
    renderToolTrace(record);
  } else {
    renderError(record);
  }
}

loadXlsxInspection();
