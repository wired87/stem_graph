(() => {
  const csrf = (form) => form.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  const outputFor = (form) => form.querySelector("[data-result]") || document.querySelector("[data-global-result]");
  const setStatus = (message, state = "") => {
    const el = document.querySelector("#system-status");
    if (!el) return;
    el.className = `status ${state}`.trim();
    el.innerHTML = `<span></span> ${message}`;
  };

  document.querySelectorAll(".js-api-form").forEach((form) => form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = form.querySelector("[data-error]");
    if (error) error.hidden = true;
    const button = form.querySelector("button[type=submit]");
    if (button) button.disabled = true;
    setStatus("Processing", "is-running");
    try {
      const multipart = form.dataset.mode === "multipart";
      const options = { method: "POST", headers: { "X-CSRFToken": csrf(form) } };
      if (multipart) options.body = new FormData(form);
      else {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(Object.fromEntries(new FormData(form)));
      }
      const response = await fetch(form.dataset.endpoint, options);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || data.detail || `Request failed (${response.status})`);
      const output = outputFor(form);
      if (output) output.textContent = JSON.stringify(data, null, 2);
      setStatus("Complete");
    } catch (exception) {
      if (error) { error.textContent = exception.message; error.hidden = false; }
      const output = outputFor(form);
      if (output) output.textContent = exception.message;
      setStatus("Needs attention", "is-error");
    } finally {
      if (button) button.disabled = false;
    }
  }));

  document.querySelectorAll(".js-config-form").forEach((form) => form.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const genes = String(data.get("ensembl_entries") || "").split(/\s+/).filter(Boolean);
    const functions = String(data.get("functional_annotation") || "").split(/\n|,/).map(v => v.trim()).filter(Boolean);
    const config = { protein: {
      ensembl_entries: Object.fromEntries(genes.map(id => [id, { id }])),
      functional_annotation: functions,
      function_similarity_threshold: Number(data.get("function_similarity_threshold") || .75),
      fetch_go_xrefs: data.has("fetch_go_xrefs"),
    }};
    form.querySelector("[data-result]").textContent = JSON.stringify(config, null, 2);
    setStatus("Configuration ready");
  }));
})();
