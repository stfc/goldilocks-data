const datasets = [
  {
    id: "qe-scf-kindex-pseudodojo",
    code: "Quantum ESPRESSO",
    task: "SCF · k-points",
    title: "Γ-inclusive k-index · PseudoDojo",
    description:
      "No-spin PBEsol SCF sweeps over distinct Γ-inclusive meshes, labelled from per-atom energy stability.",
    structures: 16208,
    snapshot: "1 Sep 2026",
    tags: ["PseudoDojo 0.4", "PBEsol", "SR standard", "cold smearing"],
    summary:
      "https://raw.githubusercontent.com/stfc/goldilocks-data/main/campaigns/qe/kpoints/results/source-summary.csv",
    notebook:
      "https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/notebooks/analysis.ipynb",
  },
  {
    id: "qe-scf-kindex-sssp",
    code: "Quantum ESPRESSO",
    task: "SCF · k-points",
    title: "k-mesh convergence · SSSP",
    description:
      "Reference campaign using the SSSP 1.3 PBEsol precision library, retained for cross-library convergence analysis.",
    structures: 18220,
    snapshot: "reference dataset",
    tags: ["SSSP 1.3", "PBEsol", "precision", "reference"],
    notebook:
      "https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/notebooks/analysis.ipynb",
  },
];

const state = { code: "All", task: "All" };
const codeFilters = document.querySelector("#code-filters");
const taskFilters = document.querySelector("#task-filters");
const datasetGrid = document.querySelector("#dataset-grid");
const catalogStatus = document.querySelector("#catalog-status");

const options = (key) => ["All", ...new Set(datasets.map((dataset) => dataset[key]))];

function makeFilters(container, key) {
  options(key).forEach((value) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `chip${value === "All" ? " active" : ""}`;
    button.textContent = value;
    button.setAttribute("aria-pressed", String(value === "All"));
    button.addEventListener("click", () => {
      state[key] = value;
      container.querySelectorAll(".chip").forEach((chip) => {
        const selected = chip === button;
        chip.classList.toggle("active", selected);
        chip.setAttribute("aria-pressed", String(selected));
      });
      renderDatasets();
    });
    container.appendChild(button);
  });
}

function datasetCard(dataset) {
  const article = document.createElement("article");
  article.className = "dataset-card";
  article.innerHTML = `
    <div>
      <span class="kicker">${dataset.code} · ${dataset.task}</span>
      <h3>${dataset.title}</h3>
      <p>${dataset.description}</p>
      <div class="tags">${dataset.tags.map((tag) => `<span class="tag">${tag}</span>`).join("")}</div>
    </div>
    <div class="dataset-count">
      <strong>${dataset.structures.toLocaleString()}</strong>
      <small>structure${dataset.structures === 1 ? "" : "s"}<br>${dataset.snapshot}</small>
    </div>
    <div class="dataset-links">
      ${dataset.summary ? `<a href="${dataset.summary}">Data ↗</a>` : ""}
      ${dataset.notebook ? `<a href="${dataset.notebook}">Method ↗</a>` : ""}
    </div>`;
  return article;
}

function renderDatasets() {
  const visible = datasets.filter(
    (dataset) =>
      (state.code === "All" || dataset.code === state.code) &&
      (state.task === "All" || dataset.task === state.task),
  );
  datasetGrid.replaceChildren();
  catalogStatus.textContent = `${visible.length} dataset${visible.length === 1 ? "" : "s"} shown`;
  if (!visible.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No published dataset matches this code and task yet.";
    datasetGrid.appendChild(empty);
    return;
  }
  visible.forEach((dataset) => datasetGrid.appendChild(datasetCard(dataset)));
}

makeFilters(codeFilters, "code");
makeFilters(taskFilters, "task");
renderDatasets();
