(() => {
  const form = document.querySelector("#stemcnv-step");
  document.querySelector("[data-workflow-panel='stemcnv']").hidden = false;
  const result = document.querySelector("[data-stemcnv-result]");
  const tray = document.querySelector("[data-stemcnv-table]");
  const eventList = document.querySelector("[data-stemcnv-events]");
  const statusText = document.querySelector("[data-stemcnv-status]");
  const loader = document.querySelector("[data-stemcnv-loader]");
  const responseFields = document.querySelector("[data-stemcnv-response]");
  const error = form.querySelector("[data-error]");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;
  const summary = form.querySelector("[data-file-summary]");
  const fileInput = form.querySelector("input[type=file]");
  const confirmButton = form.querySelector("[data-confirm]");
  const outputPanel = document.querySelector(".workflow-output");
  const dropZone = form.querySelector("[data-drop-zone]");
  const fileInputs = [fileInput];

  const readEntry = async (entry) => {
    if (entry.isFile) return [await new Promise((resolve, reject) => entry.file(resolve, reject))];
    if (!entry.isDirectory) return [];
    const reader = entry.createReader();
    const entries = [];
    while (true) {
      const batch = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
      if (!batch.length) break;
      entries.push(...batch);
    }
    return (await Promise.all(entries.map(readEntry))).flat();
  };
  dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fileInput.click(); }
  });
  for (const name of ["dragenter", "dragover"]) dropZone.addEventListener(name, (event) => {
    event.preventDefault(); dropZone.classList.add("is-dragging");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("is-dragging"));
  dropZone.addEventListener("drop", async (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
    const entries = [...event.dataTransfer.items]
      .map((item) => item.webkitGetAsEntry?.()).filter(Boolean);
    const files = entries.length
      ? (await Promise.all(entries.map(readEntry))).flat()
      : [...event.dataTransfer.files];
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    fileInput.files = transfer.files;
    updateFileSummary();
  });

  const updateFileSummary = () => {
    const count = fileInputs.reduce((total, input) => total + input.files.length, 0);
    summary.textContent = count
      ? `${count} file${count === 1 ? "" : "s"} selected.`
      : "No files selected — the canonical StemCNV example data will be used.";
  };
  fileInputs.forEach((input) => input.addEventListener("change", updateFileSummary));

  const renderState = (state) => {
    const running = ["queued", "starting", "running", "created", "cancelling"].includes(state.status);
    confirmButton.disabled = running;
    loader.hidden = !running;
    outputPanel.classList.toggle("is-complete", state.status === "complete");
    statusText.textContent = running
      ? "StemCNV is working. This page updates by itself."
      : state.status === "complete"
        ? "Finished successfully. Every step passed and your ZIP file is ready below."
        : state.status === "failed"
          ? "StemCNV could not finish. Open the latest steps below and ask the server owner for help."
          : `Current state: ${state.status || "waiting"}`;
    eventList.replaceChildren();
    const events = (state.events || []).slice(-8);
    for (const event of events) {
      const item = document.createElement("li");
      const time = document.createElement("time");
      time.textContent = new Date(event.at).toLocaleTimeString();
      const label = document.createElement("b");
      label.textContent = event.type.replaceAll("_", " ");
      item.append(time, " ", label, ` — ${event.message}`);
      eventList.append(item);
    }
    if (!events.length) eventList.append(Object.assign(document.createElement("li"), {textContent: "Waiting for the container…"}));
    const fields = [
      ["Job number", state.run_id], ["Progress state", state.status], ["Files used", state.input_source],
      ["Download name", state.output_name], ["Engine result", state.exit_code],
      ["Files in the ZIP", state.artifacts?.length]
    ];
    responseFields.replaceChildren();
    for (const [label, value] of fields) {
      if (value === undefined) continue;
      responseFields.append(
        Object.assign(document.createElement("dt"), {textContent: label}),
        Object.assign(document.createElement("dd"), {textContent: String(value)})
      );
    }
    responseFields.hidden = false;
    result.textContent = JSON.stringify(state, null, 2);
  };

  const requestJson = async (url, options = {}) => {
    const response = await fetch(url, options);
    if (response.status === 204) return null;
    const data = await response.json();
    if (!response.ok) {
      const validation = data.errors && Object.values(data.errors).flat(Infinity).join(" ");
      throw new Error(validation || data.error || data.detail || data.message || `Request failed (${response.status})`);
    }
    return data;
  };

  const monitor = async (initial) => {
    let state = initial;
    renderState(state);
    while (["queued", "starting", "running", "created", "cancelling"].includes(state.status)) {
      await new Promise((resolve) => setTimeout(resolve, 5000));
      state = await requestJson(`/api/product/status-run/${state.run_id}/`);
      renderState(state);
    }
    if (state.status === "complete") {
      tray.hidden = false;
      tray.replaceChildren();
      const download = document.createElement("a");
      download.className = "dispense";
      download.href = state.artifacts_url;
      download.textContent = `Download the finished ZIP: ${state.output_name || "StemCNV results"}`;
      tray.append(download);
      if (state.artifacts?.length) {
        const list = document.createElement("ul");
        for (const artifact of state.artifacts) list.append(Object.assign(document.createElement("li"), {textContent: artifact}));
        tray.append(list);
      }
    }
    return state;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    tray.hidden = true;
    confirmButton.disabled = true;
    loader.hidden = false;
    statusText.textContent = "Preparing the files and placing the job in the queue…";
    const selectedCount = fileInputs.reduce((total, input) => total + input.files.length, 0);
    result.textContent = selectedCount
      ? "Uploading your folder and arranging it for StemCNV…"
      : "Preparing the official StemCNV example data…";
    try {
      const job = await requestJson(form.dataset.endpoint, {
        method: "POST", headers: {"X-CSRFToken": csrf}, body: new FormData(form),
      });
      await monitor(job);
    } catch (exception) {
      error.textContent = exception.message;
      error.hidden = false;
      loader.hidden = true;
      statusText.textContent = "The job could not be started. Read the message below or ask the server owner for help.";
      result.textContent = exception.message;
    } finally {
      if (!statusText.textContent.startsWith("Analysis is running")) confirmButton.disabled = false;
    }
  });

  requestJson("/api/product/latest-run/")
    .then((state) => { if (state) monitor(state); })
    .catch((exception) => { statusText.textContent = `Could not restore the latest run: ${exception.message}`; });
})();
