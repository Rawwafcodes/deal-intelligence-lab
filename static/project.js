// Project detail page: loads a single project by id from the query string.

const detailEl = document.getElementById("project-detail");

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

function renderNotFound() {
  detailEl.textContent = "";
  const p = document.createElement("p");
  p.textContent = "Project not found.";
  detailEl.appendChild(p);
}

function renderProject(project) {
  detailEl.textContent = "";

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
  note.textContent =
    "Document upload and AI-assisted analysis are not part of this build yet — this page will grow to support that.";

  detailEl.append(nameEl, metaEl, descLabel, descEl, note);
}

async function loadProject() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");

  if (!id) {
    renderNotFound();
    return;
  }

  const res = await fetch(`/api/projects/${encodeURIComponent(id)}`);
  if (!res.ok) {
    renderNotFound();
    return;
  }

  const project = await res.json();
  renderProject(project);
}

loadProject();
