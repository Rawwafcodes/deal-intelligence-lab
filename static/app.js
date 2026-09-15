// Home page: lists projects and handles creating a new one.

const listEl = document.getElementById("project-list");
const emptyStateEl = document.getElementById("empty-state");
const formEl = document.getElementById("create-form");
const errorEl = document.getElementById("form-error");

function formatDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function renderProjects(projects) {
  listEl.textContent = "";
  emptyStateEl.hidden = projects.length !== 0;

  for (const project of projects) {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.className = "project-item";
    link.href = `/project.html?id=${encodeURIComponent(project.id)}`;

    const nameEl = document.createElement("div");
    nameEl.className = "name";
    nameEl.textContent = project.name;

    const descEl = document.createElement("div");
    descEl.className = "desc";
    descEl.textContent = project.description || "No description";

    const metaEl = document.createElement("div");
    metaEl.className = "meta";
    metaEl.textContent = `Created ${formatDate(project.created_at)}`;

    link.append(nameEl, descEl, metaEl);
    li.appendChild(link);
    listEl.appendChild(li);
  }
}

async function loadProjects() {
  const res = await fetch("/api/projects");
  const projects = await res.json();
  renderProjects(projects);
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorEl.textContent = "";

  const name = document.getElementById("name").value.trim();
  const description = document.getElementById("description").value.trim();

  if (!name) {
    errorEl.textContent = "Project name is required.";
    return;
  }

  const res = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    errorEl.textContent = body.error || "Something went wrong creating the project.";
    return;
  }

  formEl.reset();
  await loadProjects();
});

loadProjects();
