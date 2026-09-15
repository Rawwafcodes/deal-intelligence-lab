// Cross-document analysis results page: shows one cross-analysis record
// covering several original PDFs, with Claude's native citations linked
// back to whichever original PDF each citation actually came from.

const metaEl = document.getElementById("cross-analysis-meta");
const errorCardEl = document.getElementById("cross-analysis-error-card");
const errorTextEl = document.getElementById("cross-analysis-error-text");
const resultsCardEl = document.getElementById("cross-analysis-results-card");
const segmentsEl = document.getElementById("cross-analysis-segments");
const breadcrumbEl = document.getElementById("app-breadcrumb");

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
  too_few_documents: "At least two documents are needed for cross-document analysis.",
  too_many_documents: "Too many documents were selected for one run.",
  not_pdf: "Only PDF documents can be included in cross-document analysis.",
  oversized_total: "The selected documents are too large to send in one request.",
  encrypted_pdf: "One of the selected PDFs is password-protected or encrypted.",
  malformed_pdf: "One of the selected PDFs could not be read.",
  invalid_pdf: "Claude could not process one of the selected PDFs.",
  refused: "Claude declined to analyze these documents.",
  truncated_response: "Claude's analysis was cut off before finishing.",
  empty_response: "Claude returned no analysis text.",
  unexpected_error: "The cross-document analysis failed unexpectedly.",
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
  current.textContent = "Cross-document analysis";

  breadcrumbEl.append(homeLink, sep1, projectLink, sep2, current);
}

function pdfViewUrl(documentId, page) {
  const base = `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}/download?inline=1`;
  return page ? `${base}#page=${page}` : base;
}

function renderMeta(record) {
  metaEl.textContent = "";
  metaEl.className = "card inspection-meta";

  const title = document.createElement("div");
  title.className = "name";
  title.textContent = `Cross-document analysis (${record.document_filenames.length} documents)`;
  metaEl.appendChild(title);

  const docList = document.createElement("ul");
  docList.className = "cross-confirm-list";
  record.document_filenames.forEach((filename, index) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = pdfViewUrl(record.document_ids[index]);
    link.target = "_blank";
    link.rel = "noopener";
    link.className = "link-action";
    link.textContent = filename;
    link.title = `SHA-256: ${record.document_checksums[index]}`;
    item.appendChild(link);
    docList.appendChild(item);
  });
  metaEl.appendChild(docList);

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
}

function shortTitle(title) {
  if (!title) return "document";
  return title.length > 22 ? `${title.slice(0, 19)}…` : title;
}

function renderCitations(container, citations) {
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
      // The API returned a citation we can't map to a known document -
      // never guess which file it means; show it unlinked instead.
      link.removeAttribute("target");
      link.classList.add("citation-badge-unresolved");
    }
    link.title = `${citation.document_title || "document"} — ${citation.cited_text}`;
    const pageLabel =
      citation.end_page && citation.end_page !== citation.start_page
        ? `p. ${citation.start_page}–${citation.end_page}`
        : `p. ${citation.start_page}`;
    link.textContent = `${shortTitle(citation.document_title)} ${pageLabel}`;
    wrap.appendChild(link);
  });
  container.appendChild(wrap);
}

const HEADING_RE = /^##\s+(.*)$/;

// Matches a dash/asterisk bullet marker or a numbered-list marker ("1. ")
// at the start of a line - both are rendered the same way.
const LIST_ITEM_RE = /^(?:[-*]|\d+\.)\s+/;

// Appends text as DOM nodes, rendering **bold** spans as <strong> - never
// via innerHTML, since this text ultimately derives from PDF content and
// must be treated as inert data, not markup to execute.
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

// Like appendInlineFormatted, but also breaks to a new line before each
// "\n"-separated piece - used so the labeled fields of a finding template
// (**Title:**, **Classification:**, ...) each start on their own line
// instead of running together as one wall of text, even though the API
// merged them into a single uncited content block (see joinTextParts).
function appendMultilineFormatted(container, text) {
  text.split("\n").forEach((line, index) => {
    if (index > 0) container.appendChild(document.createElement("br"));
    appendInlineFormatted(container, line);
  });
}

const FIELD_LABEL_RE = /^\*\*[^*]+:\*\*/;

// Joins a block's buffered lines back into one string, but starts a new
// line before any piece that looks like a "**Label:**" finding field
// (e.g. the review mandate's Title/Classification/Severity/... template),
// so those fields render as a scannable list rather than run together.
function joinTextParts(parts) {
  return parts.reduce((acc, part, index) => {
    if (index === 0) return part;
    return acc + (FIELD_LABEL_RE.test(part) ? "\n" : " ") + part;
  }, "");
}

function renderContentBlock(text, citations, section) {
  const isBullet = LIST_ITEM_RE.test(text);
  const wrapper = document.createElement(isBullet ? "div" : "p");
  wrapper.className = isBullet ? "inspection-bullet" : "inspection-paragraph";

  const textSpan = document.createElement("span");
  appendMultilineFormatted(textSpan, isBullet ? text.replace(LIST_ITEM_RE, "") : text);
  wrapper.appendChild(textSpan);

  renderCitations(wrapper, citations);

  const isFinding =
    isBullet &&
    (section.toLowerCase().includes("potential inconsistencies") ||
      section.toLowerCase().includes("unsupported cross-document claims"));
  if (isFinding && (!citations || citations.length === 0)) {
    const uncited = document.createElement("span");
    uncited.className = "citation-badge uncited";
    uncited.textContent = "uncited";
    wrapper.appendChild(uncited);
  }

  segmentsEl.appendChild(wrapper);
}

// Concatenating every text block's `text` in order reproduces Claude's full
// reply exactly - citations only annotate substrings of that one continuous
// stream, not paragraph/heading/bullet boundaries (see inspect.js for the
// single-document version of this same finding). So markdown structure has
// to be found by re-splitting the reconstructed stream into lines, not by
// treating each API content block as its own rendering unit. Each line
// keeps the citations (and, here, the source document) of every block that
// contributed characters to it.
function streamToLines(segments) {
  const lines = [[]];
  segments.forEach((segment) => {
    const parts = segment.text.split("\n");
    parts.forEach((part, index) => {
      if (index > 0) lines.push([]);
      if (part) lines[lines.length - 1].push({ text: part, citations: segment.citations || [] });
    });
  });
  return lines.map((pieces) => ({
    text: pieces.map((p) => p.text).join(""),
    citations: pieces.flatMap((p) => p.citations),
  }));
}

function renderSegments(record) {
  segmentsEl.textContent = "";
  const lines = streamToLines(record.segments);
  let section = "";
  let block = null; // { textParts: string[], citations: [] } | null

  const closeBlock = () => {
    if (!block) return;
    const text = joinTextParts(block.textParts).trim();
    const citations = block.citations;
    block = null;
    if (text) renderContentBlock(text, citations, section);
  };

  lines.forEach((line) => {
    const trimmed = line.text.trim();
    const headingMatch = HEADING_RE.exec(trimmed);

    if (headingMatch) {
      closeBlock();
      section = headingMatch[1].trim();
      const heading = document.createElement("h3");
      heading.className = "inspection-heading";
      heading.textContent = section;
      segmentsEl.appendChild(heading);
      return;
    }

    if (!trimmed) {
      closeBlock(); // blank line: paragraph break
      return;
    }

    if (LIST_ITEM_RE.test(trimmed)) {
      closeBlock(); // a new bullet always starts its own block
      block = { textParts: [trimmed], citations: [...line.citations] };
    } else if (block) {
      block.textParts.push(trimmed); // continuation of the open paragraph/bullet
      block.citations.push(...line.citations);
    } else {
      block = { textParts: [trimmed], citations: [...line.citations] };
    }
  });
  closeBlock();
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
    renderSegments(record);
  }
}

async function loadCrossAnalysis() {
  if (!projectId || !analysisId) {
    metaEl.textContent = "";
    const p = document.createElement("p");
    p.textContent = "Missing project or analysis reference.";
    metaEl.appendChild(p);
    return;
  }

  const [projectRes, analysisRes] = await Promise.all([
    fetch(`/api/projects/${encodeURIComponent(projectId)}`),
    fetch(`/api/projects/${encodeURIComponent(projectId)}/cross-analyses/${encodeURIComponent(analysisId)}`),
  ]);

  setBreadcrumb(projectRes.ok ? (await projectRes.json()).name : "Project");

  if (!analysisRes.ok) {
    metaEl.textContent = "";
    const p = document.createElement("p");
    p.textContent = "Cross-document analysis not found.";
    metaEl.appendChild(p);
    return;
  }

  const record = await analysisRes.json();
  renderMeta(record);

  if (record.status === "success") {
    resultsCardEl.hidden = false;
    renderSegments(record);
  } else {
    renderError(record);
  }
}

loadCrossAnalysis();
