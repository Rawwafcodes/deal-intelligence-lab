// Inspection results page: shows one PDF-inspection record, including
// Claude's native citations linked back to the original PDF.

const metaEl = document.getElementById("inspection-meta");
const errorCardEl = document.getElementById("inspection-error-card");
const errorTextEl = document.getElementById("inspection-error-text");
const resultsCardEl = document.getElementById("inspection-results-card");
const segmentsEl = document.getElementById("inspection-segments");
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
  oversized_pdf: "This PDF is too large to send for inspection.",
  encrypted_pdf: "This PDF is password-protected or encrypted.",
  malformed_pdf: "This PDF could not be read.",
  invalid_pdf: "Claude could not process this PDF.",
  refused: "Claude declined to analyze this document.",
  truncated_response: "Claude's analysis was cut off before finishing.",
  empty_response: "Claude returned no analysis text.",
  unexpected_error: "The inspection failed unexpectedly.",
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
  current.textContent = "Inspection";

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
  title.textContent = record.document_filename;
  metaEl.appendChild(title);

  const viewLink = document.createElement("a");
  viewLink.href = pdfViewUrl(record.document_id);
  viewLink.target = "_blank";
  viewLink.rel = "noopener";
  viewLink.className = "link-action";
  viewLink.textContent = "View original PDF";
  metaEl.appendChild(viewLink);

  const list = document.createElement("dl");
  list.className = "inspection-facts";

  const facts = [
    ["Model", record.model],
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

function renderCitations(container, citations, documentId) {
  if (!citations || citations.length === 0) return;
  const wrap = document.createElement("span");
  wrap.className = "citation-list";
  citations.forEach((citation) => {
    const link = document.createElement("a");
    link.className = "citation-badge";
    link.target = "_blank";
    link.rel = "noopener";
    link.href = pdfViewUrl(documentId, citation.start_page);
    link.title = citation.cited_text;
    link.textContent =
      citation.end_page && citation.end_page !== citation.start_page
        ? `p. ${citation.start_page}–${citation.end_page}`
        : `p. ${citation.start_page}`;
    wrap.appendChild(link);
  });
  container.appendChild(wrap);
}

const HEADING_RE = /^##\s+(.*)$/;

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

function renderContentBlock(text, citations, section, documentId) {
  const isBullet = /^[-*]\s+/.test(text);
  const wrapper = document.createElement(isBullet ? "div" : "p");
  wrapper.className = isBullet ? "inspection-bullet" : "inspection-paragraph";

  const textSpan = document.createElement("span");
  appendInlineFormatted(textSpan, isBullet ? text.replace(/^[-*]\s+/, "") : text);
  wrapper.appendChild(textSpan);

  renderCitations(wrapper, citations, documentId);

  const isMaterialStatement = isBullet && section.toLowerCase().includes("material factual statements");
  if (isMaterialStatement && (!citations || citations.length === 0)) {
    const uncited = document.createElement("span");
    uncited.className = "citation-badge uncited";
    uncited.textContent = "uncited";
    wrapper.appendChild(uncited);
  }

  segmentsEl.appendChild(wrapper);
}

// Concatenating every text block's `text` in order reproduces Claude's
// full reply exactly - citations only annotate substrings of that one
// continuous stream (confirmed against a live response: a citation's
// span can land on a trailing "(page 1)" note rather than the factual
// sentence right before it, because that's just where the API's citation
// boundary happened to fall in the stream, not a paragraph or bullet
// boundary). So markdown structure (headings, blank-line paragraph
// breaks, "- " bullets) has to be found by re-splitting that reconstructed
// stream into lines, not by treating each API block as a rendering unit.
// Each resulting line keeps the citations of every block that contributed
// characters to it, so a citation is never dropped or misattached.
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
    const text = block.textParts.join(" ").trim();
    const citations = block.citations;
    block = null;
    if (text) renderContentBlock(text, citations, section, record.document_id);
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

    if (/^[-*]\s+/.test(trimmed)) {
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

async function loadInspection() {
  if (!projectId || !inspectionId) {
    metaEl.textContent = "";
    const p = document.createElement("p");
    p.textContent = "Missing project or inspection reference.";
    metaEl.appendChild(p);
    return;
  }

  const [projectRes, inspectionRes] = await Promise.all([
    fetch(`/api/projects/${encodeURIComponent(projectId)}`),
    fetch(`/api/projects/${encodeURIComponent(projectId)}/inspections/${encodeURIComponent(inspectionId)}`),
  ]);

  setBreadcrumb(projectRes.ok ? (await projectRes.json()).name : "Project");

  if (!inspectionRes.ok) {
    metaEl.textContent = "";
    const p = document.createElement("p");
    p.textContent = "Inspection not found.";
    metaEl.appendChild(p);
    return;
  }

  const record = await inspectionRes.json();
  renderMeta(record);

  if (record.status === "success") {
    resultsCardEl.hidden = false;
    renderSegments(record);
  } else {
    renderError(record);
  }
}

loadInspection();
