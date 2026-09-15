// Home page: lists projects and handles creating a new one.

const listEl = document.getElementById("project-list");
const emptyStateEl = document.getElementById("empty-state");
const formEl = document.getElementById("create-form");
const errorEl = document.getElementById("form-error");
const newProjectDialogEl = document.getElementById("new-project-dialog");
const newProjectButtonEl = document.getElementById("new-project-button");
const emptyStateNewProjectButtonEl = document.getElementById("empty-state-new-project");
const cancelCreateButtonEl = document.getElementById("cancel-create");

function formatDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function renderProjects(projects) {
  listEl.textContent = "";
  emptyStateEl.hidden = projects.length !== 0;

  projects.forEach((project, index) => {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.className = "project-item";
    link.href = `/project.html?id=${encodeURIComponent(project.id)}`;
    link.style.setProperty("--stagger-i", Math.min(index, 10));

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
  });
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
  newProjectDialogEl.close();
  await loadProjects();
});

function openNewProjectDialog() {
  formEl.reset();
  errorEl.textContent = "";
  newProjectDialogEl.showModal();
  document.getElementById("name").focus();
}

newProjectButtonEl.addEventListener("click", openNewProjectDialog);
emptyStateNewProjectButtonEl.addEventListener("click", openNewProjectDialog);
cancelCreateButtonEl.addEventListener("click", () => newProjectDialogEl.close());

newProjectDialogEl.addEventListener("click", (event) => {
  const rect = newProjectDialogEl.getBoundingClientRect();
  const inDialog =
    rect.top <= event.clientY &&
    event.clientY <= rect.top + rect.height &&
    rect.left <= event.clientX &&
    event.clientX <= rect.left + rect.width;
  if (!inDialog) newProjectDialogEl.close();
});

loadProjects();

// AI connection test

const testConnectionButtonEl = document.getElementById("test-connection-button");
const connectionResultEl = document.getElementById("connection-result");

testConnectionButtonEl.addEventListener("click", async () => {
  testConnectionButtonEl.disabled = true;
  testConnectionButtonEl.textContent = "Testing…";
  connectionResultEl.textContent = "";
  connectionResultEl.className = "";

  try {
    const res = await fetch("/api/ai/test-connection", { method: "POST" });
    const result = await res.json();
    renderConnectionResult(result);
  } catch (err) {
    connectionResultEl.className = "connection-result status-error";
    connectionResultEl.textContent = "Could not reach the local app server.";
  } finally {
    testConnectionButtonEl.disabled = false;
    testConnectionButtonEl.textContent = "Test AI connection";
  }
});

function renderConnectionResult(result) {
  connectionResultEl.textContent = "";

  if (result.success) {
    connectionResultEl.className = "connection-result status-success";
    const lines = [
      "Connected successfully.",
      `Model: ${result.model}`,
      result.usage
        ? `Tokens used: ${result.usage.input_tokens} in / ${result.usage.output_tokens} out`
        : "",
      result.matched_expected
        ? "Response matched the expected confirmation text."
        : `Unexpected reply: "${result.reply_text}"`,
    ].filter(Boolean);
    for (const line of lines) {
      const p = document.createElement("p");
      p.textContent = line;
      connectionResultEl.appendChild(p);
    }
  } else {
    connectionResultEl.className = "connection-result status-error";
    const p = document.createElement("p");
    p.textContent = result.error_message || "The connection test failed.";
    connectionResultEl.appendChild(p);
  }
}
