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

function renderSegments(record) {
  segmentsEl.textContent = "";
  let currentSection = "";

  record.segments.forEach((segment) => {
    const trimmed = segment.text.trim();
    const headingMatch = HEADING_RE.exec(trimmed);

    if (headingMatch) {
      currentSection = headingMatch[1].trim();
      const heading = document.createElement("h3");
      heading.className = "inspection-heading";
      heading.textContent = currentSection;
      segmentsEl.appendChild(heading);
      return;
    }

    if (!trimmed) return;

    const isBullet = /^[-*]\s+/.test(trimmed);
    const wrapper = document.createElement(isBullet ? "div" : "p");
    wrapper.className = isBullet ? "inspection-bullet" : "inspection-paragraph";

    const textSpan = document.createElement("span");
    textSpan.textContent = isBullet ? trimmed.replace(/^[-*]\s+/, "") : segment.text;
    wrapper.appendChild(textSpan);

    renderCitations(wrapper, segment.citations, record.document_id);

    const isMaterialStatement =
      isBullet && currentSection.toLowerCase().includes("material factual statements");
    if (isMaterialStatement && (!segment.citations || segment.citations.length === 0)) {
      const uncited = document.createElement("span");
      uncited.className = "citation-badge uncited";
      uncited.textContent = "uncited";
      wrapper.appendChild(uncited);
    }

    segmentsEl.appendChild(wrapper);
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
