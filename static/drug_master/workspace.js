(() => {
  const form = document.querySelector("#drug-form");
  if (!form) return;
  const button = document.querySelector("#run-button");
  const status = document.querySelector("#system-status");
  const error = document.querySelector("#error-message");
  const empty = document.querySelector("#empty-state");
  const content = document.querySelector("#result-content");
  const download = document.querySelector("#download-button");
  let lastPayload = null;

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    button.disabled = true;
    status.className = "status is-running";
    status.innerHTML = "<span></span> Acquiring evidence";
    try {
      const rawVariants = form.elements.namedItem("vep_annotations").value.trim();
      const body = {
        accessions: form.elements.namedItem("accessions").value,
        sex: form.elements.namedItem("sex").value,
        vep_annotations: rawVariants ? JSON.parse(rawVariants) : [],
      };
      const response = await fetch(form.dataset.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value,
        },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status})`);
      lastPayload = data;
      const summary = data.summary;
      const artifacts = data.artifacts || {};
      document.querySelector("#artifact-links").innerHTML = Object.values(artifacts).map(
        (artifact) => `<a class="secondary" href="${escapeHtml(artifact.url)}" ${artifact.filename.endsWith(".html") ? 'target="_blank" rel="noopener"' : "download"}>${escapeHtml(artifact.filename)}</a>`
      ).join("");
      document.querySelector("#metric-grid").innerHTML = [
        ["Nodes", summary.nodes], ["Edges", summary.edges],
        ["Targets", summary.targets], ["Drugs", summary.drugs],
      ].map(([label, value]) => `<div class="metric"><b>${value}</b><span>${label}</span></div>`).join("");
      document.querySelector("#clinical-warning").textContent = data.result.warning;
      const matrix = data.result.ingredient_matrix;
      document.querySelector("#matrix-head").innerHTML = `<tr><th>Drug / factor</th>${matrix.columns.map(
        (column) => `<th>${escapeHtml(column)}</th>`
      ).join("")}</tr>`;
      document.querySelector("#matrix-body").innerHTML = matrix.rows.map((row) => `
        <tr><td>${escapeHtml(row.drug_id)} · ${Number(row.research_exposure_factor).toFixed(2)}</td>
        ${matrix.columns.map((column) => `<td>${Number(row.target_scores[column] || 0).toFixed(4)}</td>`).join("")}</tr>
      `).join("") || `<tr><td colspan="${matrix.columns.length + 1}">No eligible drug candidate found.</td></tr>`;
      empty.hidden = true;
      content.hidden = false;
      download.disabled = false;
      status.className = "status";
      status.innerHTML = "<span></span> Complete";
      document.querySelector("#results").scrollIntoView({ behavior: "smooth" });
    } catch (exception) {
      error.textContent = exception.message;
      error.hidden = false;
      status.className = "status is-error";
      status.innerHTML = "<span></span> Failed";
    } finally {
      button.disabled = false;
    }
  });

  download.addEventListener("click", () => {
    if (!lastPayload) return;
    const blob = new Blob([JSON.stringify(lastPayload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "precision-drug-graph.json";
    anchor.click();
    URL.revokeObjectURL(url);
  });
})();
