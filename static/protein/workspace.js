(() => {
  const form = document.querySelector("#protein-form");
  if (!form) return;

  const chips = [...document.querySelectorAll("[data-value]")];
  const customTissue = document.querySelector("#custom-tissue");
  const annotation = document.querySelector("#functional-annotation");
  const proteinType = document.querySelector("#protein-type");
  const button = document.querySelector("#run-button");
  const status = document.querySelector("#system-status");
  const error = document.querySelector("#error-message");
  const empty = document.querySelector("#empty-state");
  const summary = document.querySelector("#result-summary");
  const list = document.querySelector("#protein-list");
  const download = document.querySelector("#download-button");
  let selectedTissue = "Thalamus";
  let lastPayload = null;

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");

  chips.forEach((chip) => chip.addEventListener("click", () => {
    chips.forEach((item) => item.classList.remove("is-selected"));
    chip.classList.add("is-selected");
    selectedTissue = chip.dataset.value;
    customTissue.value = "";
  }));
  customTissue.addEventListener("input", () => {
    if (customTissue.value.trim()) {
      chips.forEach((item) => item.classList.remove("is-selected"));
      selectedTissue = customTissue.value.trim();
    }
  });

  const renderProteins = (proteins) => {
    list.innerHTML = proteins.map((protein, index) => `
      <li class="protein-card">
        <div class="protein-card__top">
          <div>
            <h3>${String(index + 1).padStart(2, "0")} · ${escapeHtml(protein.id)}</h3>
            <p>${escapeHtml(protein.description || "Unknown protein")}</p>
          </div>
          <span class="protein-card__score">${Math.round(Number(protein.score || 0) * 100)}% evidence</span>
        </div>
        <p class="protein-card__text"><strong>Gene:</strong> ${escapeHtml(protein.gene || "unknown")}</p>
        <p class="protein-card__text">${escapeHtml(protein.text || "No functional comment available.")}</p>
      </li>
    `).join("");
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    error.hidden = true;
    status.className = "status is-running";
    status.innerHTML = "<span></span> Synthesizing";
    const body = {
      tissue: customTissue.value.trim() || selectedTissue,
      functional_annotation: annotation.value.trim(),
      protein_type: proteinType.value,
    };

    try {
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
      const proteins = Array.isArray(data.proteins) ? data.proteins : [];
      lastPayload = { query: body, proteins };
      empty.hidden = true;
      summary.hidden = false;
      summary.textContent = `${proteins.length} candidates · ${body.tissue || "all tissues"} · ${body.protein_type || "all classes"}`;
      renderProteins(proteins);
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
    anchor.download = "proteinmaster-results.json";
    anchor.click();
    URL.revokeObjectURL(url);
  });
})();
