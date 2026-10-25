import { createLocalUI } from "./local-ui.js";
export function createPipelineUI({
  state,
  api,
  escape: e,
  badge,
  date,
  field,
  dialog,
  saved,
  toast,
  reload,
  navigate,
  can,
}) {
  const $ = (selector) => document.querySelector(selector);
  const localUI = createLocalUI({
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
  });
  const button = (action, id, label, disabled = false) =>
    `<button class="button small ghost" data-pipeline="${action}" data-id="${e(id)}" ${disabled ? "disabled" : ""}>${e(label)}</button>`;
  const row = (label, value) =>
    `<div class="detail-row"><span>${e(label)}</span><span>${value}</span></div>`;
  const panel = (title, content, actions = "") =>
    `<div class="panel"><div class="panel-heading"><h2>${e(title)}</h2><div class="actions">${actions}</div></div>${content}</div>`;
  const value = (v, suffix = "") =>
    v === null || v === undefined ? "Not available" : `${e(v)}${suffix}`;
  const time = (v) => (v ? date(v) : "No sample");
  const stageState = (snapshot) => {
    if (!snapshot) return badge("Not reported", "neutral");
    return badge(
      snapshot.state.replaceAll("_", " "),
      snapshot.state === "error"
        ? "danger"
        : ["disabled", "not_started", "stopped"].includes(snapshot.state)
          ? "neutral"
          : "",
    );
  };
  function pending() {
    const sections = state.pipeline?.pending_restart || [];
    const local = state.pipeline?.pending_local || [];
    return (
      (local.length
        ? `<div class="notice">Local settings awaiting apply: ${e(local.join(", "))}. Applying enabled camera or microphone settings opens those devices. ${button("apply-local", "", "Apply local changes")}</div>`
        : "") +
      (sections.length
        ? `<div class="notice">Saved settings awaiting runtime restart: ${e(sections.join(", "))}. The active hardware and processing settings are shown separately.</div>`
        : "")
    );
  }
  function overview() {
    const r = state.runtime,
      p = state.pipeline;
    if (!r) return "";
    const rows = [
      [
        "Service",
        badge(
          r.runtime.healthy ? "Running" : "Fault",
          r.runtime.healthy ? "" : "danger",
        ),
      ],
    ];
    if (p?.host)
      rows.push(
        ["Host", e(p.host)],
        ["System", `${e(p.platform)} · ${e(p.machine)}`],
        ["Python", e(p.python)],
      );
    if (r.runtime.uptime_s !== undefined)
      rows.push(["Service uptime", `${Math.floor(r.runtime.uptime_s)} s`]);
    if (r.runtime.control_running) {
      rows.push(
        ["Control loop", badge("Running")],
        ["Behavior", e(r.behavior)],
        [
          "Maximum tick lateness",
          `${(r.runtime.max_tick_lateness_s * 1000).toFixed(1)} ms`,
        ],
        ["Missed control ticks", value(r.runtime.missed_ticks)],
      );
      if (r.safety)
        rows.push([
          "Emergency stop",
          badge(
            r.safety.estop ? "Latched" : "Released",
            r.safety.estop ? "danger" : "neutral",
          ),
        ]);
    }
    if (r.runtime.fault) rows.push(["Fault", e(r.runtime.fault)]);
    let html = panel(
      "Service",
      rows.map(([label, data]) => row(label, data)).join(""),
    );
    if (r.hardware_error)
      html += panel(
        "Hardware error",
        `<div class="panel-note">${e(r.hardware_error)}</div>`,
      );
    let stages = "";
    for (const [name, snapshot] of [
      ["Vision", r.perception?.vision],
      ["Speech recognition", r.perception?.speech],
    ]) {
      if (
        snapshot &&
        !["disabled", "not_started", "stopped"].includes(snapshot.state)
      )
        stages += `<div class="pipeline-stage"><span>${name}${snapshot.last_sample_at ? `<small>Last sample ${time(snapshot.last_sample_at)}</small>` : ""}${snapshot.error ? `<small>${e(snapshot.error)}</small>` : ""}</span>${stageState(snapshot)}</div>`;
    }
    const llm = p?.runtime_llm;
    if (llm?.provider === "openai_compat")
      stages += row("LLM", `<code>${e(llm.model)}</code>`);
    if (stages) html += panel("Active processing", stages);
    return (
      pending() +
      `<div class="overview-grid">${html}</div>` +
      (p ? '<div id="live-slot"></div>' : "")
    );
  }
  function connections() {
    const selected = state.pipeline?.runtime_connection;
    const rows = state.connections
      .map((c) => {
        const applied =
          c.id === selected &&
          c.updated_at === state.pipeline.runtime_connection_revision;
        const check = c.check;
        return `<tr><td><strong>${e(c.name)}</strong><small class="muted">${e(c.provider)}</small></td><td class="wrap"><code>${e(c.base_url)}</code></td><td>${c.model ? `<code>${e(c.model)}</code>` : "Not selected"}</td><td>${applied ? badge("Selected") : c.id === selected ? badge("Changes not applied", "warn") : badge("Not selected", "neutral")}</td><td>${check ? badge(check.ok ? "Reachable" : "Failed", check.ok ? "" : "danger") + `<small class="muted">${date(check.at)} · ${check.latency_ms} ms</small>${check.error ? `<small class="muted wrap">${e(check.error)}</small>` : ""}` : "Not checked"}</td><td>${c.has_api_key ? "Stored" : "Not set"}</td><td><div class="row-actions">${button("check-connection", c.id, "Check / models")}${button("edit-connection", c.id, "Edit")}${!applied ? button("select-connection", c.id, "Select", !c.model) : button("disable-llm", "", "Disable")}${button("delete-connection", c.id, "Delete", c.id === selected)}</div></td></tr>`;
      })
      .join("");
    return panel(
      "Configured connections",
      `<div class="table-scroll"><table><thead><tr>${["Connection", "Endpoint", "Model", "Runtime", "Last check", "API key", ""].map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows || '<tr><td class="empty" colspan="7">No LLM connections configured.</td></tr>'}</tbody></table></div>`,
    );
  }
  function local() {
    const p = state.pipeline;
    const dependencies = (p.dependencies || []).filter((d) =>
      ["opencv", "cameras", "faces", "whisper", "audio"].includes(d.id),
    );
    const rows = dependencies
      .map(
        (d) =>
          `<tr><td>${e(d.name)}</td><td>${badge(d.error ? "Import failed" : d.installed ? "Installed" : "Not installed", d.error ? "danger" : d.installed ? "" : "neutral")}</td><td>${e(d.version || (d.installed ? "Not reported" : "—"))}</td><td class="wrap">${e(d.error || (d.import_checked ? "Import verified" : "Not tested"))}</td><td>${localUI.installButton(d)}</td></tr>`,
      )
      .join("");
    const vision = p.local.vision,
      speech = p.local.speech;
    return (
      pending() +
      panel(
        "Local dependencies",
        `<div class="table-scroll"><table><thead><tr><th>Package</th><th>Availability</th><th>Version</th><th>Check</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`,
        button("dependencies", "", "Check imports"),
      ) +
      `<div class="overview-grid">${panel("Vision", row("Worker", stageState(vision)) + row("Object detector", e(p.active_config.vision.detector)) + row("Face recognition", e(p.active_config.vision.faces_enabled ? "Enabled" : "Disabled")) + row("Last frame", time(vision.last_sample_at)) + (vision.last_sample_at ? row("Frame size", `${vision.frame_width} × ${vision.frame_height}`) + row("Processing time", `${vision.processing_ms.toFixed(1)} ms`) + row("Detections", String(vision.detections.length)) : "") + (vision.error ? `<div class="panel-note warning">${e(vision.error)}</div>` : ""), button("config", "vision", "Configure") + localUI.controls("vision") + localUI.liveButton("vision"))}
      ${panel("Speech recognition", row("Worker", stageState(speech)) + row("Engine", e(p.active_config.speech.stt)) + row("Model", p.active_config.speech.stt !== "none" ? `<code>${e(p.active_config.speech.stt_model)}</code>` : "Not selected") + row("Last audio", time(speech.last_sample_at)) + (speech.last_sample_at ? row("Processing time", `${speech.processing_ms.toFixed(1)} ms`) + row("Last transcript", e(speech.transcript || "(no speech detected)")) : "") + (speech.error ? `<div class="panel-note warning">${e(speech.error)}</div>` : ""), button("config", "speech", "Configure") + localUI.controls("speech") + localUI.liveButton("speech"))}</div>` +
      localUI.models("vision") +
      localUI.models("speech") +
      localUI.operations()
    );
  }
  function hardware() {
    const p = state.pipeline,
      h = p.hardware;
    const devices = h.physical
      ? [
          [
            "Motors",
            h.motors.driver,
            h.motors.output
              ? `Duty ${h.motors.output.left.toFixed(3)} / ${h.motors.output.right.toFixed(3)}`
              : "No output reported",
          ],
          [
            "Encoders",
            h.encoders.driver,
            h.encoders.counts
              ? `Counts ${h.encoders.counts.join(" / ")}`
              : "No counts reported",
          ],
          [
            "Range sensor",
            h.range.driver,
            h.range.distance_mm !== null
              ? `${h.range.distance_mm} mm · sample age ${h.range.sample_age_s?.toFixed(2)} s`
              : "No valid sample",
          ],
        ]
      : [];
    const readings = devices
      .map(
        ([name, driver, reading]) =>
          `<tr><td>${e(name)}</td><td><code>${e(driver)}</code></td><td>${e(reading)}</td></tr>`,
      )
      .join("");
    let html =
      pending() +
      panel(
        "Physical devices",
        `<div class="table-scroll"><table><thead><tr><th>Device</th><th>Driver</th><th>Reading</th></tr></thead><tbody>${readings || `<tr><td class="empty" colspan="3">${h.error ? e(h.error) : "No physical devices configured."}</td></tr>`}</tbody></table></div>`,
      );
    html += panel(
      "Configuration",
      [
        ["Motor driver and GPIO", "hardware"],
        ["Wheel geometry and encoders", "drive"],
        ["Safety limits and watchdog", "safety"],
        ["Camera", "camera"],
      ]
        .map(
          ([title, section]) =>
            `<div class="settings-section"><div><h3>${title}</h3>${section === "camera" ? `<small>${e(p.active_config.vision.source)} · ${p.active_config.vision.enabled ? "enabled" : "disabled"}</small>` : ""}</div><div class="actions">${section === "camera" ? button("camera-check", "", "Capture test frame") : ""}${button("config", section, "Configure")}</div></div>`,
        )
        .join(""),
    );
    if (h.video_devices?.length)
      html += panel(
        "OS video device nodes",
        `<div class="panel-note">${h.video_devices.map(e).join(", ")}</div>`,
      );
    return html;
  }
  function render(page) {
    if (!["connections", "local", "hardware"].includes(page)) return "";
    if (!state.pipeline || state.pipeline.error)
      return panel(
        "Pipeline",
        `<div class="panel-note">${e(state.pipeline?.error || "Pipeline status unavailable.")}</div>`,
      );
    return page === "connections"
      ? connections()
      : page === "local"
        ? local()
        : hardware();
  }
  function connectionDialog(connection) {
    const endpoints = {
      ollama: "http://localhost:11434/v1",
      lmstudio: "http://localhost:1234/v1",
      openai: "https://api.openai.com/v1",
      openai_compat: "",
    };
    dialog(
      connection ? "Edit LLM connection" : "Add LLM connection",
      field(
        "Connection name",
        "name",
        "text",
        connection?.name || "",
        'required maxlength="80"',
      ) +
        `<label>Provider<select name="provider" id="provider-select">${[
          ["ollama", "Ollama"],
          ["lmstudio", "LM Studio"],
          ["openai", "OpenAI"],
          ["openai_compat", "OpenAI-compatible endpoint"],
        ]
          .map(
            ([id, label]) =>
              `<option value="${id}" ${connection?.provider === id ? "selected" : ""}>${label}</option>`,
          )
          .join("")}</select></label>` +
        field(
          "Base URL",
          "base_url",
          "url",
          connection?.base_url || endpoints.ollama,
          'required maxlength="500"',
        ) +
        field(
          "Model ID",
          "model",
          "text",
          connection?.model || "",
          'maxlength="256" list="known-models"',
        ) +
        `<datalist id="known-models">${(connection?.check?.models || []).map((m) => `<option value="${e(m)}"></option>`).join("")}</datalist>` +
        field(
          connection?.has_api_key
            ? "API key (leave blank to keep stored key)"
            : "API key",
          "api_key",
          "password",
          "",
          'autocomplete="new-password" maxlength="4096"',
        ) +
        (connection?.has_api_key
          ? '<label class="checkbox"><input name="clear_api_key" type="checkbox">Remove stored API key</label>'
          : "") +
        field(
          "Request timeout (seconds)",
          "timeout_s",
          "number",
          connection?.timeout_s || 20,
          'required min="0.1" max="120" step="0.1"',
        ),
      async (form) => {
        const data = Object.fromEntries(form);
        data.timeout_s = Number(data.timeout_s);
        data.clear_api_key = form.has("clear_api_key");
        if (!data.api_key) delete data.api_key;
        await api(
          `/api/admin/pipeline/connections${connection ? "/" + connection.id : ""}`,
          connection ? "PUT" : "POST",
          data,
        );
        await saved(
          "Connection saved. Check the endpoint to retrieve its model list.",
        );
      },
      "Save connection",
    );
    $("#provider-select").addEventListener("change", (event) => {
      $("#modal [name=base_url]").value = endpoints[event.target.value];
    });
  }
  function resolved(schema, root) {
    if (schema.$ref)
      return resolved(root.$defs[schema.$ref.split("/").at(-1)], root);
    if (schema.anyOf)
      return {
        ...resolved(
          schema.anyOf.find((v) => v.type !== "null"),
          root,
        ),
        nullable: schema.anyOf.some((v) => v.type === "null"),
      };
    return schema;
  }
  function schemaFields(schema, values, root, prefix = "", keys = null) {
    return Object.entries(schema.properties)
      .filter(([key]) => !keys || keys.includes(key))
      .map(([key, s]) => {
        const spec = resolved(s, root),
          name = prefix + key,
          current = values[key],
          label = spec.title || key;
        if (spec.type === "object")
          return `<div class="config-group"><h3>${e(label)}</h3><div class="form-columns">${schemaFields(spec, current, root, name + ".")}</div></div>`;
        if (spec.type === "boolean")
          return `<label class="checkbox"><input data-config-type="boolean" name="${name}" type="checkbox" ${current ? "checked" : ""}>${e(label)}</label>`;
        if (spec.enum)
          return `<label>${e(label)}<select data-config-type="string" name="${name}">${spec.enum.map((v) => `<option value="${e(v)}" ${current === v ? "selected" : ""}>${e(v)}</option>`).join("")}</select></label>`;
        const type = ["number", "integer"].includes(spec.type)
          ? "number"
          : "text";
        const extras = `data-config-type="${spec.type}" ${spec.nullable ? 'data-nullable="true"' : "required"} ${type === "number" ? `step="${spec.type === "integer" ? "1" : "any"}"` : ""} ${spec.minimum !== undefined ? `min="${spec.minimum}"` : ""} ${spec.maximum !== undefined ? `max="${spec.maximum}"` : ""}`;
        return (
          field(
            label,
            name,
            type,
            Array.isArray(current) ? JSON.stringify(current) : (current ?? ""),
            extras,
          ) +
          (spec.description
            ? `<p class="field-hint">${e(spec.description)}</p>`
            : "")
        );
      })
      .join("");
  }
  function configDialog(section) {
    const camera = section === "camera";
    const key = camera ? "vision" : section;
    let keys = null;
    if (camera)
      keys = [
        "enabled",
        "source",
        "camera_index",
        "width",
        "height",
        "max_fps",
      ];
    if (section === "vision")
      keys = [
        "detector",
        "model_path",
        "model_config_path",
        "labels_path",
        "input_width",
        "input_height",
        "input_scale",
        "input_mean",
        "swap_rb",
        "confidence_threshold",
        "faces_enabled",
        "known_faces_path",
        "face_tolerance",
      ];
    if (section === "speech")
      keys = [
        "enabled",
        "stt",
        "stt_model",
        "input_device",
        "chunk_s",
        "language",
      ];
    const schema = state.schema[key];
    dialog(
      `Configure ${camera ? "camera" : { hardware: "hardware", drive: "drivetrain", safety: "safety", vision: "vision", speech: "speech recognition" }[key]}`,
      `<p class="field-hint">${["vision", "speech"].includes(key) ? "Save settings, then apply local changes to activate them." : "Saved values take effect after the runtime is restarted."}</p>` +
        schemaFields(schema, state.pipeline.config[key], schema, "", keys),
      async (form) => {
        const data = {};
        for (const input of $("#modal-form").querySelectorAll(
          "[data-config-type]",
        )) {
          let v = input.type === "checkbox" ? input.checked : input.value;
          if (v === "" && input.dataset.nullable) v = null;
          else if (["number", "integer"].includes(input.dataset.configType))
            v = Number(v);
          else if (input.dataset.configType === "array") v = JSON.parse(v);
          const parts = input.name.split(".");
          let target = data;
          for (const part of parts.slice(0, -1)) target = target[part] ||= {};
          target[parts.at(-1)] = v;
        }
        await api(`/api/admin/pipeline/config/${key}`, "PUT", data);
        await saved(
          ["vision", "speech"].includes(key)
            ? "Local settings saved. Apply changes to activate them."
            : "Settings saved for the next runtime start.",
        );
      },
      ["vision", "speech"].includes(key) ? "Save settings" : "Save for restart",
    );
  }
  $("#content").addEventListener("click", async (event) => {
    const source = event.target.closest("[data-pipeline]");
    if (!source) return;
    const name = source.dataset.pipeline,
      id = source.dataset.id;
    if (name === "edit-connection") {
      connectionDialog(state.connections.find((c) => c.id === id));
      return;
    }
    if (name === "config") {
      if (["vision", "speech", "camera"].includes(id)) {
        await localUI.configure(id);
        return;
      }
      configDialog(id);
      return;
    }
    if (name === "delete-connection") {
      const connection = state.connections.find((c) => c.id === id);
      dialog(
        "Delete connection?",
        `<p>${e(connection.name)} and its stored credential will be removed.</p>`,
        async () => {
          await api(`/api/admin/pipeline/connections/${id}`, "DELETE");
          await saved("Connection deleted.");
        },
        "Delete",
        true,
      );
      return;
    }
    source.disabled = true;
    try {
      if (name === "check-connection") {
        const check = await api(
          `/api/admin/pipeline/connections/${id}/check`,
          "POST",
        );
        await reload();
        navigate(state.page);
        dialog(
          "Connection check",
          `<p>${e(check.ok ? "Endpoint returned a model list." : check.error)}</p><div class="status-result">${e(check.models.join("\n") || (check.ok ? "No models reported." : ""))}</div>`,
          null,
        );
      }
      if (name === "select-connection" || name === "disable-llm") {
        await api("/api/admin/pipeline/selection", "POST", {
          connection_id: name === "disable-llm" ? null : id,
        });
        await reload();
        navigate(state.page);
        toast(name === "disable-llm" ? "LLM disabled." : "LLM selected.");
      }
      if (name === "apply-local") {
        await api("/api/admin/pipeline/local/apply", "POST");
        await reload();
        navigate(state.page);
        toast("Local settings applied.");
      }
      if (name === "dependencies") {
        await api("/api/admin/pipeline/dependencies/check", "POST");
        await reload();
        navigate(state.page);
      }
      if (name === "camera-check") {
        const result = await api("/api/admin/pipeline/camera/check", "POST");
        dialog(
          "Camera capture",
          `<p>${e(result.device || "Camera")} · ${e(result.width || result.frame_width)} × ${e(result.height || result.frame_height)} · ${date(result.captured_at || result.last_sample_at)}</p><img class="camera-preview" src="/api/admin/pipeline/camera/frame?at=${Date.now()}" alt="Latest frame from the selected camera">`,
          null,
        );
      }
    } catch (error) {
      toast(error.message, true);
    } finally {
      if (source.isConnected) source.disabled = false;
    }
  });
  return {
    render,
    overview,
    connectionDialog,
    afterRender: localUI.mountLive,
  };
}
