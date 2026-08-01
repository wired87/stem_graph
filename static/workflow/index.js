(() => {
  const tabs = [...document.querySelectorAll("[data-workflow-tab]")];
  const panels = [...document.querySelectorAll("[data-workflow-panel]")];
  const csrf = (form) => form.querySelector("[name=csrfmiddlewaretoken]")?.value || "";

  const activate = (name) => {
    tabs.forEach((tab) => {
      const active = tab.dataset.workflowTab === name;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.workflowPanel !== name;
    });
  };
  tabs.forEach((tab) => tab.addEventListener("click", () => activate(tab.dataset.workflowTab)));

  const requestJson = async (endpoint, options) => {
    const response = await fetch(endpoint, options);
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || data.detail || `Request failed (${response.status})`);
    }
    return data;
  };
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
  const formatCell = (value) => escapeHtml(
    typeof value === "string" ? value : JSON.stringify(value)
  );
  const renderStemGraphTable = (target, table) => {
    if (!target || !table?.rows) return;
    const legend = table.legend?.node_value_meanings || {};
    const legendHtml = Object.entries(legend).map(([nodeId, entry]) => {
      const values = entry.values || entry.coding || {};
      const valuesHtml = Object.entries(values).map(
        ([key, label]) => `<li><code>${escapeHtml(key)}</code>: ${escapeHtml(label)}</li>`
      ).join("");
      return `<section><h4>${escapeHtml(nodeId)}</h4><p>${escapeHtml(entry.semantics || entry.method || entry.warning || "")}</p><ul>${valuesHtml}</ul></section>`;
    }).join("");
    const rowHtml = table.rows.map((row) => `
      <tr>
        <td>${row.tdx}</td>
        <td>${escapeHtml(row.batch_id)}</td>
        <td>${escapeHtml(row.batch_type)}</td>
        <td>${escapeHtml(row.item_id || "")}</td>
        <td>${formatCell(row.value)}</td>
        <td>${escapeHtml(row.value_label || "")}</td>
      </tr>
    `).join("");
    target.hidden = false;
    target.innerHTML = `
      <div class="stem-graph-table__legend">
        <p>${escapeHtml(table.legend?.tdx || "")}</p>
        ${legendHtml}
      </div>
      <table>
        <thead><tr><th>tdx</th><th>batch</th><th>type</th><th>item</th><th>value</th><th>meaning</th></tr></thead>
        <tbody>${rowHtml}</tbody>
      </table>
    `;
  };

  const proteinForm = document.querySelector("#protein-step");
  const drugForm = document.querySelector("#drug-step");
  const proteinDrugResult = document.querySelector("[data-protein-drug-result]");
  const picker = document.querySelector("[data-protein-candidates]");

  proteinForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = proteinForm.querySelector("[data-error]");
    error.hidden = true;
    const button = proteinForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const values = Object.fromEntries(new FormData(proteinForm));
      delete values.csrfmiddlewaretoken;
      const data = await requestJson(proteinForm.dataset.endpoint, {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf(proteinForm)},
        body: JSON.stringify(values),
      });
      const proteins = Array.isArray(data.proteins) ? data.proteins : [];
      const proteinArtifacts = document.querySelector("[data-protein-artifacts]");
      proteinArtifacts.innerHTML = data.aum_pdf?.url
        ? `<a href="${data.aum_pdf.url}" download>${data.aum_pdf.filename}</a>`
        : "";
      picker.innerHTML = proteins.length
        ? proteins.map((protein) => `<label><input type="checkbox" name="accession" value="${String(protein.id).replaceAll('"', '&quot;')}" checked><span>${protein.id} · ${protein.gene || "unknown"}</span></label>`).join("")
        : "No protein candidates were returned.";
      drugForm.classList.toggle("is-locked", proteins.length === 0);
      drugForm.querySelector("button[type=submit]").disabled = proteins.length === 0;
      proteinDrugResult.textContent = JSON.stringify({stage: "protein_prediction", proteins}, null, 2);
    } catch (exception) {
      error.textContent = exception.message;
      error.hidden = false;
    } finally {
      button.disabled = false;
    }
  });

  drugForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = drugForm.querySelector("[data-error]");
    error.hidden = true;
    const accessions = [...picker.querySelectorAll("[name=accession]:checked")].map((item) => item.value);
    if (!accessions.length) {
      error.textContent = "Select at least one protein candidate.";
      error.hidden = false;
      return;
    }
    const button = drugForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const rawVep = drugForm.elements.namedItem("vep_annotations").value.trim();
      const data = await requestJson(drugForm.dataset.endpoint, {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf(drugForm)},
        body: JSON.stringify({
          accessions,
          sex: drugForm.elements.namedItem("sex").value,
          vep_annotations: rawVep ? JSON.parse(rawVep) : [],
        }),
      });
      const artifactTray = document.querySelector("[data-drug-artifacts]");
      artifactTray.innerHTML = Object.values(data.artifacts || {}).map(
        (artifact) => `<a href="${artifact.url}" ${artifact.filename.endsWith(".html") ? 'target="_blank" rel="noopener"' : "download"}>${artifact.filename}</a>`
      ).join("");
      proteinDrugResult.textContent = JSON.stringify(data, null, 2);
    } catch (exception) {
      error.textContent = exception.message;
      error.hidden = false;
    } finally {
      button.disabled = false;
    }
  });

  const stemForm = document.querySelector("#stemcnv-step");
  const stemResult = document.querySelector("[data-stemcnv-result]");
  const stemTable = document.querySelector("[data-stemcnv-table]");
  stemForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = stemForm.querySelector("[data-error]");
    error.hidden = true;
    const button = stemForm.querySelector("button[type=submit]");
    button.disabled = true;
    stemTable.hidden = true;
    stemTable.innerHTML = "";
    stemResult.textContent = "Building the StemCNV graph…";
    try {
      const data = await requestJson(stemForm.dataset.endpoint, {
        method: "POST",
        headers: {"X-CSRFToken": csrf(stemForm)},
        body: new FormData(stemForm),
      });
      renderStemGraphTable(stemTable, data.stem_graph_table);
      stemResult.textContent = JSON.stringify(data, null, 2);
    } catch (exception) {
      error.textContent = exception.message;
      error.hidden = false;
      stemResult.textContent = exception.message;
    } finally {
      button.disabled = false;
    }
  });
})();
