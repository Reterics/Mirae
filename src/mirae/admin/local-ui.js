export function createLocalUI({
  state,
  api,
  escape: e,
  badge,
  field,
  dialog,
  saved,
  toast,
  reload,
  navigate,
}) {
  const $ = (selector) => document.querySelector(selector);
  const button = (action, id, label, disabled = false) =>
    `<button type="button" class="button small ghost" data-local="${action}" data-id="${e(id)}" ${disabled ? "disabled" : ""}>${e(label)}</button>`;
  const option = (id, label, selected) =>
    `<option value="${e(id)}" ${selected ? "selected" : ""}>${e(label)}</option>`;
  const panel = (title, content) =>
    `<div class="panel"><div class="panel-heading"><h2>${e(title)}</h2></div>${content}</div>`;
  function models(kind, compact = false) {
    if (compact) {
      return panel(
        "Available models",
        (state.pipeline.models || [])
          .filter((m) => m.kind === kind)
          .map(
            (m) =>
              `<div class="model-choice"><div><strong>${e(m.name)}</strong><small>${(m.bytes / 1e6).toFixed(1)} MB · ${m.installed ? "Downloaded" : "Not downloaded"}${m.recommended ? " · Recommended for CPU" : ""}</small></div>${button("download", m.id, m.installed ? "Download again" : "Download")}</div>`,
          )
          .join(""),
      );
    }
    const rows = (state.pipeline.models || [])
      .filter((m) => m.kind === kind)
      .map(
        (m) =>
          `<tr><td><strong>${e(m.name)}</strong>${m.recommended ? '<small class="muted">Recommended for CPU</small>' : ""}</td><td>${(m.bytes / 1e6).toFixed(1)} MB</td><td>${badge(m.installed ? "Downloaded" : "Not downloaded", m.installed ? "" : "neutral")}</td><td><a href="${e(m.source)}" target="_blank" rel="noreferrer">${e(m.license)} · source</a></td><td><div class="row-actions">${button("download", m.id, m.installed ? "Download again" : "Download")}${button("activate", m.id, "Activate", !m.installed)}</div></td></tr>`,
      )
      .join("");
    return panel(
      kind === "vision"
        ? "Object detection models"
        : "Speech recognition models",
      `<div class="table-scroll"><table><thead><tr><th>Model</th><th>Download</th><th>Availability</th><th>License</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`,
    );
  }
  function operations() {
    const jobs = state.pipeline.jobs || [];
    return jobs.length
      ? panel(
          "Operations",
          `<div class="table-scroll"><table><thead><tr><th>Operation</th><th>Target</th><th>Status</th><th></th></tr></thead><tbody>${jobs.map((j) => `<tr><td>${e(j.kind)}</td><td>${e(j.target)}</td><td>${badge(j.state, j.state === "failed" ? "danger" : "neutral")}</td><td>${button("job", j.id, "View console")}</td></tr>`).join("")}</tbody></table></div>`,
        )
      : "";
  }
  function controls(kind) {
    const enabled = state.pipeline.active_config[kind].enabled;
    return (
      button(
        "toggle",
        kind,
        enabled ? "Stop" : kind === "vision" ? "Start camera" : "Start",
      ) + (kind === "speech" ? button("audio", "", "Test microphone") : "")
    );
  }
  function liveButton(kind) {
    return button(
      "live",
      kind,
      kind === "vision" ? "View on Runtime" : "Live transcript",
    );
  }
  const boxColors = { object: "#e0a100", face: "#2f80ed", known: "#27ae60" };
  async function drawFrame(canvas, data) {
    const bytes = Uint8Array.from(atob(data.frame), (c) => c.charCodeAt(0));
    const bitmap = await createImageBitmap(
      new Blob([bytes], { type: "image/jpeg" }),
    );
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(bitmap, 0, 0);
    bitmap.close();
    const scale = Math.max(1, canvas.width / 480);
    ctx.lineWidth = 2 * scale;
    ctx.font = `${Math.round(11 * scale)}px sans-serif`;
    ctx.textBaseline = "top";
    for (const d of data.detections || []) {
      const [x, y, w, h] = [
        d.box[0] * canvas.width,
        d.box[1] * canvas.height,
        d.box[2] * canvas.width,
        d.box[3] * canvas.height,
      ];
      ctx.strokeStyle = ctx.fillStyle =
        d.kind === "face"
          ? d.label === "unidentified face"
            ? boxColors.face
            : boxColors.known
          : boxColors.object;
      ctx.strokeRect(x, y, w, h);
      const text = detectionLabel(d);
      const pad = 3 * scale,
        height = 11 * scale + 2 * pad;
      const top = y - height >= 0 ? y - height : y;
      ctx.fillRect(x, top, ctx.measureText(text).width + 2 * pad, height);
      ctx.fillStyle = "#ffffff";
      ctx.fillText(text, x + pad, top + pad);
    }
  }
  function detectionLabel(d) {
    if (d.confidence !== null)
      return `${d.label} ${Math.round(d.confidence * 100)}%`;
    if (d.match_distance !== null)
      return `${d.label} d=${d.match_distance.toFixed(2)}`;
    return d.label;
  }
  // Runtime page live output. One element is kept across the page's periodic
  // re-renders so the camera canvas and transcript do not flicker or reset.
  const live = {
    element: null,
    visionTimer: null,
    speechTimer: null,
    busy: false,
    shown: null,
    cursor: 0,
    lines: [],
  };
  const part = (name) => live.element.querySelector(`[data-live="${name}"]`);
  function buildLive() {
    const element = document.createElement("div");
    element.className = "overview-grid";
    element.innerHTML = `<div class="panel"><div class="panel-heading"><h2>Camera output</h2><div class="actions"><label class="live-rate">Refresh<select data-live="rate">${option("0", "Paused", false)}${option("1", "1 frame/s", false)}${option("2", "2 frames/s", true)}${option("5", "5 frames/s", false)}</select></label><button type="button" class="button small ghost" data-live="snapshot">Snapshot</button><button type="button" class="button small ghost" data-local="toggle" data-id="vision" data-live="vision-toggle">Start</button></div></div><div class="live-body"><p class="field-hint" data-live="vision-status" role="status">Connecting…</p><canvas class="camera-preview" data-live="canvas" width="640" height="480" hidden aria-label="Latest camera frame with detection boxes"></canvas><div class="status-result" data-live="detections"></div><p class="field-hint">Boxes: amber objects, blue unidentified faces, green known faces.</p></div></div><div class="panel"><div class="panel-heading"><h2>Speech recognition output</h2><div class="actions">${liveButton("speech")}<button type="button" class="button small ghost" data-local="toggle" data-id="speech" data-live="speech-toggle">Start</button></div></div><div class="live-body"><p class="field-hint" data-live="speech-status" role="status">Connecting…</p><label class="field-hint">Level of the last chunk<progress data-live="level" max="1" value="0"></progress></label><pre class="operation-console live-recent" data-live="recent" aria-label="Latest transcribed speech"></pre></div></div>`;
    element.querySelector('[data-live="rate"]').onchange = scheduleLive;
    element.querySelector('[data-live="snapshot"]').onclick = pullVision;
    return element;
  }
  function stopLive() {
    clearInterval(live.visionTimer);
    clearInterval(live.speechTimer);
    live.visionTimer = live.speechTimer = null;
  }
  const tickLive = (pull) => () => {
    if (live.element.isConnected) pull();
    else stopLive();
  };
  function scheduleLive() {
    stopLive();
    const fps = Number(part("rate").value);
    if (fps) live.visionTimer = setInterval(tickLive(pullVision), 1000 / fps);
    live.speechTimer = setInterval(tickLive(pullSpeech), 1000);
  }
  function mountLive() {
    const slot = $("#live-slot");
    if (!slot) return;
    live.element ??= buildLive();
    slot.replaceWith(live.element);
    if (!live.speechTimer) {
      scheduleLive();
      pullVision();
      pullSpeech();
    }
  }
  async function pullVision() {
    if (live.busy) return;
    live.busy = true;
    const status = part("vision-status"),
      canvas = part("canvas");
    try {
      const data = await api("/api/admin/pipeline/live/vision");
      if (data.frame && data.samples !== live.shown) {
        live.shown = data.samples;
        await drawFrame(canvas, data);
        canvas.hidden = false;
        part("detections").textContent =
          (data.detections || [])
            .map((d) => `${detectionLabel(d)} · ${d.kind}`)
            .join("\n") || "No detections in this frame.";
      }
      const config = state.pipeline.active_config.vision;
      part("vision-toggle").textContent = config.enabled
        ? "Stop"
        : "Start camera";
      status.textContent = data.error
        ? data.error
        : data.state === "running"
          ? `Frame ${data.samples} · ${data.frame_width} × ${data.frame_height} · ${data.processing_ms.toFixed(0)} ms · object detection ${config.detector === "none" ? "off" : "on"} · face recognition ${config.faces_enabled ? "on" : "off"} · ${new Date(data.last_sample_at * 1000).toLocaleTimeString()}`
          : "Vision is not running. Start the camera under Local processing.";
    } catch (error) {
      status.textContent = error.message;
    } finally {
      live.busy = false;
    }
  }
  async function pullSpeech() {
    const status = part("speech-status");
    try {
      const data = await api(
        "/api/admin/pipeline/live/speech?after=" + live.cursor,
      );
      live.cursor = data.cursor;
      for (const entry of data.entries)
        live.lines.push(
          `${new Date(entry.at * 1000).toLocaleTimeString()}  ${entry.text || "(no speech)"}`,
        );
      live.lines = live.lines.slice(-6);
      part("recent").textContent =
        live.lines.join("\n") || "No transcribed audio yet.";
      if (data.peak !== undefined) part("level").value = data.peak;
      part("speech-toggle").textContent = state.pipeline.active_config.speech
        .enabled
        ? "Stop"
        : "Start";
      status.textContent = data.error
        ? data.error
        : data.state === "listening"
          ? `Listening on ${data.device || "microphone"} · ${data.samples} chunks of ${state.pipeline.active_config.speech.chunk_s} s`
          : "Speech recognition is not running. Start it under Local processing.";
    } catch (error) {
      status.textContent = error.message;
    }
  }
  function liveSpeech() {
    const chunk = state.pipeline.active_config.speech.chunk_s;
    dialog(
      "Live transcript",
      `<p id="live-status" class="field-hint" role="status">Connecting…</p><label>Level of the last chunk<progress id="live-level" max="1" value="0"></progress></label><pre id="live-transcript" class="operation-console" role="log" aria-label="Transcribed speech"></pre><p class="field-hint">Whisper transcribes ${e(chunk)} s chunks, so text appears one chunk plus processing time after it is spoken.</p>`,
      null,
    );
    const log = $("#live-transcript"),
      status = $("#live-status"),
      level = $("#live-level");
    let cursor = 0;
    (async () => {
      while (log.isConnected) {
        try {
          const data = await api(
            "/api/admin/pipeline/live/speech?after=" + cursor,
          );
          if (!log.isConnected) return;
          cursor = data.cursor;
          const bottom =
            log.scrollHeight - log.scrollTop - log.clientHeight < 40;
          for (const entry of data.entries)
            log.textContent += `${new Date(entry.at * 1000).toLocaleTimeString()}  ${entry.text || "(no speech)"}  · ${(entry.processing_ms / 1000).toFixed(1)} s\n`;
          if (bottom) log.scrollTop = log.scrollHeight;
          if (data.peak !== undefined) level.value = data.peak;
          status.textContent = data.error
            ? data.error
            : data.state === "listening"
              ? `Listening on ${data.device || "microphone"} · ${data.samples} chunks${data.dropped_blocks ? ` · ${data.dropped_blocks} audio blocks dropped` : ""}`
              : "Speech recognition is not running. Start it under Local processing.";
        } catch (error) {
          if (status.isConnected) status.textContent = error.message;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    })();
  }
  function installButton(dependency) {
    return button(
      "install",
      dependency.id,
      dependency.installed ? "Reinstall" : "Install",
    );
  }
  function cameraPicker(config) {
    const devices = state.pipeline.devices.cameras;
    return `<label>Camera<select name="camera_device">${option("", devices.items.length ? "Default — " + devices.items[0].name : "Default — no camera detected", !config.camera_device)}${devices.items.map((c) => option(c.id, c.name + " · " + c.source, config.camera_device === c.id)).join("")}</select></label>${devices.error ? `<p class="form-error">${e(devices.error)}</p>` : ""}`;
  }
  function microphonePicker(config) {
    const devices = state.pipeline.devices.audio,
      first = devices.items.find((d) => d.default);
    return `<label>Microphone<select name="input_device">${option("", first ? "System default — " + first.name : "System default", config.input_device === null)}${devices.items.map((d) => option(d.id, d.name + " · " + d.host_api, config.input_device === d.id)).join("")}${config.input_device && !devices.items.some((d) => d.id === config.input_device) ? option(config.input_device, config.input_device + " (not connected)", true) : ""}</select></label>${devices.error ? `<p class="form-error">${e(devices.error)}</p>` : ""}`;
  }
  async function configure(section) {
    const camera = section === "camera",
      key = camera ? "vision" : section;
    dialog(
      "Discovering devices",
      '<progress aria-label="Discovering connected devices"></progress>',
      null,
    );
    try {
      state.pipeline.devices = await api(
        "/api/admin/pipeline/devices/refresh",
        "POST",
      );
    } catch (error) {
      toast(error.message, true);
      return;
    }
    const config = state.pipeline.config[key];
    const catalog = (state.pipeline.models || []).filter((m) => m.kind === key);
    // Vision may run face recognition without an object detector.
    const noDetector =
      key === "vision" && config.detector === "none" && config.faces_enabled;
    const selected = noDetector
      ? null
      : catalog.find((m) =>
          key === "vision"
            ? config.model_path?.includes(m.id)
            : config.stt_model?.includes(m.id),
        ) || catalog.find((m) => m.recommended);
    let contents =
      key === "vision" ? cameraPicker(config) : microphonePicker(config);
    if (!camera)
      contents += `<label>${key === "vision" ? "Object detection model" : "Speech model"}<select name="model_id">${key === "vision" ? option("none", "None — no object detection", noDetector) : ""}${catalog.map((m) => option(m.id, m.name + (m.installed ? " — downloaded" : " — download required"), m.id === selected?.id)).join("")}</select></label>`;
    if (key === "vision")
      contents +=
        `<div class="form-columns">${field("Width", "width", "number", config.width, 'required min="160" max="4096"')}${field("Height", "height", "number", config.height, 'required min="120" max="4096"')}${field("Frames per second", "max_fps", "number", config.max_fps, 'required min="1" max="30"')}</div>` +
        (!camera
          ? `<details><summary>Detection threshold</summary>${field("Detection confidence (object detection only)", "confidence_threshold", "number", config.confidence_threshold, 'required min="0.1" max="1" step="0.05"')}</details><details ${config.faces_enabled ? "open" : ""}><summary>Face recognition</summary><label class="checkbox"><input name="faces_enabled" type="checkbox" ${config.faces_enabled ? "checked" : ""}>Enable face_recognition</label>${field("Known face encodings (optional NPZ file)", "known_faces_path", "text", config.known_faces_path || "")}${field("Face distance tolerance", "face_tolerance", "number", config.face_tolerance, 'required min="0.1" max="1" step="0.05"')}</details>`
          : "");
    else
      contents +=
        field(
          "Audio chunk (seconds)",
          "chunk_s",
          "number",
          config.chunk_s,
          'required min="1" max="15" step="1"',
        ) +
        field(
          "Language (blank: detect automatically)",
          "language",
          "text",
          config.language || "",
          'pattern="[a-z]{2,3}" maxlength="3"',
        );
    if (!camera) contents += models(key, true);
    dialog(
      "Configure " +
        (camera
          ? "camera"
          : key === "speech"
            ? "speech recognition"
            : "vision"),
      contents,
      async (form) => {
        const skipDetector =
          key === "vision" && !camera && form.get("model_id") === "none";
        const model =
          camera || skipDetector
            ? null
            : catalog.find((m) => m.id === form.get("model_id"));
        if (!camera && !skipDetector && !model?.installed)
          throw Error("Download the selected model below, then activate it.");
        if (
          key === "vision" &&
          form.has("faces_enabled") &&
          !state.pipeline.dependencies?.find((d) => d.id === "faces")
            ?.installed
        )
          throw Error(
            "Install face_recognition under Local dependencies before enabling face recognition.",
          );
        const data = { enabled: true };
        if (key === "vision") {
          const id = form.get("camera_device");
          const device =
            state.pipeline.devices.cameras.items.find((c) => c.id === id) ||
            state.pipeline.devices.cameras.items[0];
          if (!device)
            throw Error(
              state.pipeline.devices.cameras.error ||
                "No connected camera found. Install OpenCV, connect a camera and refresh devices.",
            );
          Object.assign(data, {
            camera_device: id || null,
            source: device.source,
            width: Number(form.get("width")),
            height: Number(form.get("height")),
            max_fps: Number(form.get("max_fps")),
          });
          if (!camera)
            Object.assign(data, {
              confidence_threshold: Number(form.get("confidence_threshold")),
              faces_enabled: form.has("faces_enabled"),
              known_faces_path: form.get("known_faces_path") || null,
              face_tolerance: Number(form.get("face_tolerance")),
            });
          if (skipDetector) data.detector = "none";
        } else
          Object.assign(data, {
            input_device: form.get("input_device") || null,
            chunk_s: Number(form.get("chunk_s")),
            language: form.get("language") || null,
          });
        await api("/api/admin/pipeline/config/" + key, "PUT", data);
        if (camera || skipDetector)
          await api("/api/admin/pipeline/local/apply", "POST");
        else
          await api(
            "/api/admin/pipeline/models/" + model.id + "/activate",
            "POST",
          );
        await saved(
          key === "vision"
            ? "Camera and vision processing started."
            : "Speech recognition started.",
        );
      },
      "Save & start",
    );
  }
  async function watchJob(id) {
    dialog(
      "Operation progress",
      '<p id="operation-state" role="status">Connecting…</p><progress id="operation-progress" max="1" aria-label="Operation progress"></progress><pre id="operation-console" class="operation-console" role="log" aria-label="Live operation console"></pre><div class="actions"><button type="button" class="button" id="operation-cancel">Cancel operation</button><span class="field-hint">Closing this window leaves the operation running.</span></div>',
      null,
    );
    $("#operation-cancel").onclick = async () => {
      try {
        await api("/api/admin/pipeline/jobs/" + id + "/cancel", "POST");
      } catch (error) {
        toast(error.message, true);
      }
    };
    const consoleElement = $("#operation-console"),
      status = $("#operation-state"),
      progress = $("#operation-progress");
    let cursor = 0;
    while (consoleElement.isConnected) {
      try {
        const job = await api(
          "/api/admin/pipeline/jobs/" + id + "?after=" + cursor,
        );
        cursor = job.cursor;
        const bottom =
          consoleElement.scrollHeight -
            consoleElement.scrollTop -
            consoleElement.clientHeight <
          40;
        consoleElement.textContent +=
          job.logs.map((l) => l.line).join("\n") +
          (job.logs.length ? "\n" : "");
        if (bottom) consoleElement.scrollTop = consoleElement.scrollHeight;
        status.textContent = job.kind + " · " + job.target + " · " + job.state;
        if (job.progress === null) progress.removeAttribute("value");
        else progress.value = job.progress;
        if (!["queued", "running"].includes(job.state)) {
          $("#operation-cancel").hidden = true;
          if (job.error) status.textContent += " — " + job.error;
          await reload();
          navigate(state.page);
          return;
        }
      } catch (error) {
        status.textContent = error.message;
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  async function handle(event) {
    const source = event.target.closest("[data-local]");
    if (!source) return;
    const action = source.dataset.local,
      id = source.dataset.id;
    source.disabled = true;
    try {
      if (action === "install" || action === "download") {
        const path =
          action === "install"
            ? "dependencies/" + id + "/install"
            : "models/" + id + "/download";
        const job = await api("/api/admin/pipeline/" + path, "POST");
        await watchJob(job.job_id);
      }
      if (action === "job") await watchJob(id);
      if (action === "live") {
        if (id === "vision") navigate("overview");
        else liveSpeech();
      }
      if (action === "activate") {
        await api("/api/admin/pipeline/models/" + id + "/activate", "POST");
        await reload();
        navigate(state.page);
        toast("Model activated; processing started.");
      }
      if (action === "toggle") {
        await api("/api/admin/pipeline/local/" + id + "/enabled", "POST", {
          enabled: !state.pipeline.active_config[id].enabled,
        });
        await reload();
        navigate(state.page);
      }
      if (action === "audio") {
        dialog(
          "Microphone test",
          '<p>Capturing two seconds from the selected microphone…</p><progress aria-label="Recording microphone sample"></progress>',
          null,
        );
        const result = await api("/api/admin/pipeline/audio/check", "POST");
        dialog(
          "Microphone test",
          `<p>${e(result.device || "Active microphone")}</p><p>Sample rate: ${e(result.sample_rate)} Hz · Peak: ${result.peak === undefined ? "Waiting for an audio chunk" : (result.peak * 100).toFixed(1) + "%"}</p>${result.transcript ? `<p>${e(result.transcript)}</p>` : ""}`,
          null,
        );
      }
    } catch (error) {
      toast(error.message, true);
    } finally {
      if (source.isConnected) source.disabled = false;
    }
  }
  $("#content").addEventListener("click", handle);
  $("#modal").addEventListener("click", handle);
  return {
    models,
    operations,
    controls,
    installButton,
    liveButton,
    mountLive,
    configure,
  };
}
