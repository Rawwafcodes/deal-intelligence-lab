// Validation evaluation page: shows Claude's findings alongside the
// now-revealed answer key, lets a human rate each expected issue and each
// finding, classify unexpected findings, view the computed metrics, and
// save a human conclusion and final status. No automatic judgment happens
// here - every rating is a value the evaluator explicitly picked.

const breadcrumbEl = document.getElementById("app-breadcrumb");
const runMetaCardEl = document.getElementById("run-meta-card");
const pendingCardEl = document.getElementById("pending-card");
const answerKeyRevealCardEl = document.getElementById("answer-key-reveal-card");
const expectedIssuesListEl = document.getElementById("expected-issues-list");
const mustNotClaimReferenceListEl = document.getElementById("must-not-claim-reference-list");
const findingsCardEl = document.getElementById("findings-card");
const findingsListEl = document.getElementById("findings-list");
const metricsCardEl = document.getElementById("metrics-card");
const metricsListEl = document.getElementById("metrics-list");
const conclusionCardEl = document.getElementById("conclusion-card");
const humanConclusionEl = document.getElementById("human-conclusion");
const materialLimitationsEl = document.getElementById("material-limitations");
const recommendedImprovementsEl = document.getElementById("recommended-improvements");
const finalStatusEl = document.getElementById("final-status");
const saveErrorEl = document.getElementById("save-error");
const saveEvaluationButtonEl = document.getElementById("save-evaluation-button");
const saveStatusEl = document.getElementById("save-status");

const params = new URLSearchParams(window.location.search);
const projectId = params.get("project");
const caseId = params.get("case");
const runId = params.get("run");

const EXPECTED_ISSUE_STATUSES = [
  ["", "— Not yet rated —"],
  ["found_completely", "Found completely"],
  ["found_partially", "Found partially"],
  ["missed", "Missed"],
  ["not_applicable", "Not applicable (answer key wrong/ambiguous)"],
];
const FINDING_STATUSES = [
  ["not_reviewed", "Not yet reviewed"],
  ["correct_material", "Correct and material"],
  ["correct_immaterial", "Correct but immaterial"],
  ["partially_correct", "Partially correct"],
  ["unsupported", "Unsupported"],
  ["false", "False"],
  ["requires_specialist", "Requires specialist review"],
];
const UNEXPECTED_CLASSIFICATIONS = [
  ["", "— Not yet classified —"],
  ["newly_verified_issue", "Newly verified issue"],
  ["valid_but_immaterial", "Valid observation but immaterial"],
  ["unsupported", "Unsupported"],
  ["false", "False"],
  ["requires_investigation", "Requires further investigation"],
];
const CHECK_OPTIONS = [
  ["not_checked", "Not checked"],
  ["correct", "Correct"],
  ["incorrect", "Incorrect"],
];
const SEVERITY_CHECK_OPTIONS = [
  ["not_checked", "Not checked"],
  ["appropriate", "Appropriate"],
  ["inappropriate", "Inappropriate"],
];
const ACTION_CHECK_OPTIONS = [
  ["not_checked", "Not checked"],
  ["useful", "Useful"],
  ["not_useful", "Not useful"],
];

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
  const caseLink = document.createElement("a");
  caseLink.href = `/validation-case.html?project=${encodeURIComponent(projectId)}&case=${encodeURIComponent(caseId)}`;
  caseLink.textContent = caseName;
  const sep3 = document.createElement("span");
  sep3.className = "sep";
  sep3.textContent = "/";
  const current = document.createElement("span");
  current.className = "current";
  current.textContent = "Evaluation";
  breadcrumbEl.append(homeLink, sep1, projectLink, sep2, caseLink, sep3, current);
}

let report = null;
let expectedIssueRatings = {};
let findingRatings = {};
let unexpectedFindings = {};

function selectField(labelText, value, options, onChange) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const label = document.createElement("label");
  label.textContent = labelText;
  wrap.appendChild(label);
  const select = document.createElement("select");
  options.forEach(([optValue, optLabel]) => {
    const opt = document.createElement("option");
    opt.value = optValue;
    opt.textContent = optLabel;
    if (optValue === (value || "")) opt.selected = true;
    select.appendChild(opt);
  });
  select.addEventListener("change", () => onChange(select.value));
  wrap.appendChild(select);
  return wrap;
}

function textField(labelText, value, onChange) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const label = document.createElement("label");
  label.textContent = labelText;
  wrap.appendChild(label);
  const textarea = document.createElement("textarea");
  textarea.rows = 2;
  textarea.value = value || "";
  textarea.addEventListener("input", () => onChange(textarea.value));
  wrap.appendChild(textarea);
  return wrap;
}

function renderMeta() {
  const { case: caseData, run, analysis } = report;
  runMetaCardEl.textContent = "";
  runMetaCardEl.className = "card inspection-meta";

  const title = document.createElement("div");
  title.className = "name";
  title.textContent = `${caseData.name} — validation run`;
  runMetaCardEl.appendChild(title);

  const blindBadge = document.createElement("p");
  blindBadge.className = "section-hint";
  blindBadge.textContent = run.is_blind
    ? `Genuinely blind: the answer key was locked at ${formatDate(run.answer_key_locked_at)}, before this run started at ${formatDate(run.started_at)}.`
    : `Retrospective (not blind): this analysis and the answer-key lock timing do not establish a genuinely blind test.`;
  runMetaCardEl.appendChild(blindBadge);

  const list = document.createElement("dl");
  list.className = "inspection-facts";
  const facts = [
    ["Model", analysis.model],
    ["Mandate version", run.mandate_version],
    ["Mandate checksum", run.mandate_checksum],
    ["Answer-key version", `v${run.answer_key_version_number}`],
    ["Answer-key checksum", run.answer_key_checksum || "—"],
    ["Tokens used", analysis.input_tokens != null ? `${analysis.input_tokens} in / ${analysis.output_tokens} out` : "—"],
    ["Stop reason", analysis.stop_reason || "—"],
    ["Started", formatDate(run.started_at)],
    ["Completed", formatDate(run.completed_at)],
  ];
  for (const [label, value] of facts) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    list.append(dt, dd);
  }
  runMetaCardEl.appendChild(list);
}

function findingLinkedToAnyExpectedIssue(index) {
  return Object.values(expectedIssueRatings).some((r) => (r.linked_finding_indices || []).includes(index));
}

function renderExpectedIssues() {
  const issues = (report.answer_key.content && report.answer_key.content.issues) || [];
  const mustNotClaim = (report.answer_key.content && report.answer_key.content.must_not_claim) || [];
  const findings = report.findings || [];

  expectedIssuesListEl.textContent = "";
  issues.forEach((issue) => {
    if (!expectedIssueRatings[issue.id]) expectedIssueRatings[issue.id] = { status: null, linked_finding_indices: [], comment: "" };
    const rating = expectedIssueRatings[issue.id];

    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "12px";

    const title = document.createElement("strong");
    title.textContent = issue.title;
    card.appendChild(title);

    const facts = document.createElement("p");
    facts.className = "section-hint";
    facts.textContent = `${issue.expected_classification || "—"} · ${issue.expected_severity || "—"}`;
    card.appendChild(facts);

    if (issue.description) {
      const desc = document.createElement("p");
      desc.textContent = issue.description;
      card.appendChild(desc);
    }
    if (issue.materiality) {
      const mat = document.createElement("p");
      mat.className = "section-hint";
      mat.textContent = `Why material: ${issue.materiality}`;
      card.appendChild(mat);
    }
    if (issue.known_location) {
      const loc = document.createElement("p");
      loc.className = "section-hint";
      loc.textContent = `Known location: ${issue.known_location}`;
      card.appendChild(loc);
    }

    card.appendChild(
      selectField("Status", rating.status, EXPECTED_ISSUE_STATUSES, (v) => (rating.status = v || null))
    );

    const linkWrap = document.createElement("div");
    linkWrap.className = "field";
    const linkLabel = document.createElement("label");
    linkLabel.textContent = "Linked Claude findings";
    linkWrap.appendChild(linkLabel);
    findings.forEach((finding) => {
      const checkboxLabel = document.createElement("label");
      checkboxLabel.style.display = "block";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = (rating.linked_finding_indices || []).includes(finding.index);
      checkbox.addEventListener("change", () => {
        const set = new Set(rating.linked_finding_indices || []);
        if (checkbox.checked) set.add(finding.index);
        else set.delete(finding.index);
        rating.linked_finding_indices = Array.from(set).sort((a, b) => a - b);
        renderFindings(); // an unexpected-finding badge may need to appear/disappear
      });
      checkboxLabel.append(checkbox, ` Finding ${finding.index + 1}: ${finding.title || "(untitled)"}`);
      linkWrap.appendChild(checkboxLabel);
    });
    card.appendChild(linkWrap);

    card.appendChild(textField("Comment", rating.comment, (v) => (rating.comment = v)));

    expectedIssuesListEl.appendChild(card);
  });

  mustNotClaimReferenceListEl.textContent = "";
  if (mustNotClaim.length === 0) {
    const p = document.createElement("p");
    p.className = "section-hint";
    p.textContent = "None recorded.";
    mustNotClaimReferenceListEl.appendChild(p);
  }
  mustNotClaim.forEach((item) => {
    const p = document.createElement("p");
    p.textContent = item.statement + (item.notes ? ` — ${item.notes}` : "");
    mustNotClaimReferenceListEl.appendChild(p);
  });
}

function renderCitations(finding) {
  const wrap = document.createElement("div");
  (finding.pdf_citations || []).forEach((c) => {
    const badge = document.createElement("a");
    badge.className = "citation-badge";
    badge.target = "_blank";
    badge.rel = "noopener";
    if (c.document_id) {
      badge.href = `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(c.document_id)}/download?inline=1#page=${c.start_page}`;
    } else {
      badge.classList.add("citation-badge-unresolved");
      badge.removeAttribute("target");
    }
    badge.textContent = `${c.document_title || "PDF"} p.${c.start_page}`;
    wrap.appendChild(badge);
  });
  (finding.excel_citations || []).forEach((c) => {
    const badge = document.createElement("span");
    badge.className = "citation-badge xlsx-citation-badge";
    if (c.exists === true) badge.classList.add("xlsx-citation-verified");
    else if (c.exists === false) badge.classList.add("citation-badge-unresolved", "xlsx-citation-unverified");
    const suffix = c.exists === true ? " ✓" : c.exists === false ? " ✗" : " ?";
    badge.textContent = `${c.workbook_label}!${c.sheet}!${c.ref} [${c.kind}]${suffix}`;
    wrap.appendChild(badge);
  });
  return wrap;
}

function renderFindings() {
  const findings = report.findings || [];
  findingsListEl.textContent = "";

  findings.forEach((finding) => {
    const key = String(finding.index);
    if (!findingRatings[key]) {
      findingRatings[key] = {
        status: "not_reviewed",
        citation_check: "not_checked",
        calculation_check: "not_checked",
        severity_check: "not_checked",
        recommended_action_check: "not_checked",
        comment: "",
      };
    }
    const rating = findingRatings[key];
    const isUnexpected = !findingLinkedToAnyExpectedIssue(finding.index);

    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "12px";

    const header = document.createElement("strong");
    header.textContent = `Finding ${finding.index + 1}: ${finding.title || "(untitled)"}`;
    card.appendChild(header);

    const facts = document.createElement("p");
    facts.className = "section-hint";
    facts.textContent = `${finding.classification || "—"} · ${finding.severity || "—"}${isUnexpected ? " · UNEXPECTED (not linked to any expected issue)" : ""}`;
    card.appendChild(facts);

    if (finding.explanation) {
      const p = document.createElement("p");
      p.textContent = finding.explanation;
      card.appendChild(p);
    }
    const evidence = document.createElement("p");
    evidence.className = "section-hint";
    evidence.textContent = `PDF evidence: ${finding.pdf_evidence || "—"}`;
    card.appendChild(evidence);
    const workbookEvidence = document.createElement("p");
    workbookEvidence.className = "section-hint";
    workbookEvidence.textContent = `Workbook evidence: ${finding.workbook_evidence || "—"}`;
    card.appendChild(workbookEvidence);
    if (finding.recommended_action) {
      const action = document.createElement("p");
      action.className = "section-hint";
      action.textContent = `Recommended action: ${finding.recommended_action}`;
      card.appendChild(action);
    }

    card.appendChild(renderCitations(finding));

    card.appendChild(
      selectField("Status", rating.status, FINDING_STATUSES, (v) => (rating.status = v))
    );
    card.appendChild(
      selectField("Citation accuracy", rating.citation_check, CHECK_OPTIONS, (v) => (rating.citation_check = v))
    );
    card.appendChild(
      selectField("Calculation reproducibility", rating.calculation_check, CHECK_OPTIONS, (v) => (rating.calculation_check = v))
    );
    card.appendChild(
      selectField("Severity appropriateness", rating.severity_check, SEVERITY_CHECK_OPTIONS, (v) => (rating.severity_check = v))
    );
    card.appendChild(
      selectField("Recommended-action usefulness", rating.recommended_action_check, ACTION_CHECK_OPTIONS, (v) => (rating.recommended_action_check = v))
    );
    card.appendChild(textField("Comment", rating.comment, (v) => (rating.comment = v)));

    if (isUnexpected) {
      if (!unexpectedFindings[key]) unexpectedFindings[key] = { classification: null, comment: "" };
      const uRating = unexpectedFindings[key];
      card.appendChild(
        selectField("Unexpected-finding classification", uRating.classification, UNEXPECTED_CLASSIFICATIONS, (v) => (uRating.classification = v || null))
      );
      card.appendChild(textField("Unexpected-finding comment", uRating.comment, (v) => (uRating.comment = v)));
    }

    findingsListEl.appendChild(card);
  });
}

function renderMetric(metric) {
  const row = document.createElement("p");
  const percentText = metric.percent != null ? ` (${metric.percent}%)` : "";
  const provisionalText = metric.provisional ? " — PROVISIONAL (unreviewed findings remain)" : "";
  row.textContent = `${metric.label}: ${metric.numerator} of ${metric.denominator}${percentText}${provisionalText}`;
  return row;
}

function renderMetrics() {
  const m = report.metrics;
  metricsListEl.textContent = "";
  metricsListEl.appendChild(renderMetric(m.critical_recall));
  metricsListEl.appendChild(renderMetric(m.high_recall));
  metricsListEl.appendChild(renderMetric(m.overall_recall));
  metricsListEl.appendChild(renderMetric(m.reviewed_finding_precision));
  metricsListEl.appendChild(renderMetric(m.citation_accuracy));
  metricsListEl.appendChild(renderMetric(m.calculation_accuracy));
  metricsListEl.appendChild(renderMetric(m.severity_agreement));

  const fvp = m.fully_vs_partially_found;
  const fvpRow = document.createElement("p");
  fvpRow.textContent = `Fully found: ${fvp.fully_found}, partially found: ${fvp.partially_found}, missed: ${fvp.missed} (of ${fvp.applicable_total} applicable; ${fvp.excluded_not_applicable} excluded as not applicable)`;
  metricsListEl.appendChild(fvpRow);

  const fp = document.createElement("p");
  fp.textContent = `False-positive findings: ${m.false_positive_count.count} of ${m.false_positive_count.total_findings} total findings`;
  metricsListEl.appendChild(fp);

  const uch = document.createElement("p");
  uch.textContent = `Unsupported critical/high findings: ${m.unsupported_critical_high_count.count}`;
  metricsListEl.appendChild(uch);

  const vum = document.createElement("p");
  vum.textContent = `Verified unexpected material findings: ${m.verified_unexpected_material_findings.count}`;
  metricsListEl.appendChild(vum);

  const unreviewed = document.createElement("p");
  unreviewed.textContent = `Unreviewed findings: ${m.unreviewed_finding_count.count} of ${m.unreviewed_finding_count.total_findings}`;
  metricsListEl.appendChild(unreviewed);
}

function renderConclusion() {
  const ev = report.evaluation;
  humanConclusionEl.value = ev.human_conclusion || "";
  materialLimitationsEl.value = ev.material_limitations || "";
  recommendedImprovementsEl.value = ev.recommended_improvements || "";
  finalStatusEl.value = ev.final_status || "";
}

saveEvaluationButtonEl.addEventListener("click", async () => {
  saveErrorEl.textContent = "";
  saveStatusEl.textContent = "";
  saveEvaluationButtonEl.disabled = true;
  try {
    const res = await fetch(
      `/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(caseId)}/runs/${encodeURIComponent(runId)}/evaluation`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_issue_ratings: expectedIssueRatings,
          finding_ratings: findingRatings,
          unexpected_findings: unexpectedFindings,
          human_conclusion: humanConclusionEl.value,
          material_limitations: materialLimitationsEl.value,
          recommended_improvements: recommendedImprovementsEl.value,
          final_status: finalStatusEl.value || null,
        }),
      }
    );
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      saveErrorEl.textContent = (payload && payload.error) || "Could not save the evaluation.";
      return;
    }
    saveStatusEl.textContent = `Saved at ${formatDate(payload.updated_at)}.`;
    await loadReport(); // refresh metrics against the newly saved ratings
  } finally {
    saveEvaluationButtonEl.disabled = false;
  }
});

async function loadReport() {
  const [projectRes, reportRes] = await Promise.all([
    fetch(`/api/projects/${encodeURIComponent(projectId)}`),
    fetch(`/api/projects/${encodeURIComponent(projectId)}/validation-cases/${encodeURIComponent(caseId)}/runs/${encodeURIComponent(runId)}/report`),
  ]);

  if (!reportRes.ok) {
    pendingCardEl.hidden = false;
    return;
  }
  report = await reportRes.json();
  expectedIssueRatings = report.evaluation.expected_issue_ratings || {};
  findingRatings = report.evaluation.finding_ratings || {};
  unexpectedFindings = report.evaluation.unexpected_findings || {};

  setBreadcrumb(projectRes.ok ? (await projectRes.json()).name : "Project", report.case.name);
  renderMeta();

  answerKeyRevealCardEl.hidden = false;
  renderExpectedIssues();

  findingsCardEl.hidden = false;
  renderFindings();

  metricsCardEl.hidden = false;
  renderMetrics();

  conclusionCardEl.hidden = false;
  renderConclusion();
}

if (projectId && caseId && runId) loadReport();
