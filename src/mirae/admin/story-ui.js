// Actions page: optional things Mirae can do, each turned on or off. The Story action
// shows tonight's episode, the story's continuity notes and the voice.
export function createStoryUI({
  state,
  api,
  escape: e,
  badge,
  field,
  dialog,
  saved,
  toast,
  can,
}) {
  const $ = (selector) => document.querySelector(selector);
  const panel = (title, content, actions = "") =>
    `<div class="panel"><div class="panel-heading"><h2>${e(title)}</h2><div class="actions">${actions}</div></div>${content}</div>`;
  const row = (label, value) =>
    `<div class="detail-row"><span>${e(label)}</span><span>${value}</span></div>`;
  const button = (name, label, variant = "ghost", disabled = false) =>
    `<button class="button small ${variant}" data-story="${name}" ${disabled ? "disabled" : ""}>${e(label)}</button>`;
  const option = (value, label, selected) =>
    `<option value="${e(value)}" ${selected ? "selected" : ""}>${e(label)}</option>`;
  const engines = {
    elevenlabs: "ElevenLabs (online)",
    piper: "Piper (local, offline)",
    none: "Off",
  };
  const genres = [
    "Fantasy",
    "Science fiction",
    "Mystery",
    "Adventure",
    "Historical",
    "Fairy tale",
    "Mythology",
    "Slice of life",
  ];
  let data = null,
    actions = [],
    speech = null,
    secrets = {},
    writing = false,
    lastEpisode = null,
    timer = null;

  async function load() {
    [data, speech, secrets, { actions }] = await Promise.all([
      api("/api/story"),
      api("/api/speech"),
      can("pipeline:manage")
        ? api("/api/admin/pipeline/secrets").catch(() => ({}))
        : {},
      api("/api/actions"),
    ]);
  }

  const storyOn = () => actions.find((a) => a.id === "story")?.enabled;

  function actionList() {
    const rows = actions
      .map(
        (a) =>
          `<tr><td><strong>${e(a.name)}</strong></td><td class="muted">${e(a.description)}</td><td>${a.enabled ? badge("On") : badge("Off", "neutral")}</td><td>${can("robot:control") ? `<button class="button small ghost" data-story="toggle" data-id="${e(a.id)}">${a.enabled ? "Turn off" : "Turn on"}</button>` : ""}</td></tr>`,
      )
      .join("");
    return panel(
      "Actions",
      `<div class="table-scroll"><table><thead><tr><th>ACTION</th><th>WHAT IT DOES</th><th>STATUS</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`,
    );
  }

  function speechState() {
    if (!speech) return "";
    const labels = {
      idle: ["Ready", ""],
      off: ["Voice off", "neutral"],
      synthesizing: ["Preparing voice", ""],
      speaking: ["Speaking", ""],
      error: ["Error", "danger"],
    };
    const [label, variant] = labels[speech.state] || [speech.state, "neutral"];
    return `${badge(label, variant)} <span class="muted">${e(engines[speech.tts] || speech.tts)}</span>`;
  }

  function tonight() {
    const story = data?.story;
    const episode = lastEpisode || data?.episodes?.[0];
    let content = "";
    if (!story)
      content = `<div class="panel-note">No story yet. Start one with a premise and the main characters; Mirae continues it every night.</div>`;
    else {
      content =
        row(
          "Night",
          writing ? `${story.night + 1} · writing…` : e(story.night),
        ) +
        row("Voice", speechState()) +
        (speech?.error ? row("Voice error", e(speech.error)) : "") +
        (speech?.clip
          ? `<div class="story-audio"><audio controls preload="none" src="/api/speech/last.wav?clip=${speech.clip}"></audio>${speech.duration_s ? `<small class="muted">${e(speech.duration_s)} s · synthesized in ${e((speech.synthesis_ms / 1000).toFixed(1))} s</small>` : ""}</div>`
          : "");
      if (writing)
        content += `<div class="story-writing"><progress aria-label="Writing tonight's episode"></progress><span>Mirae is writing tonight's episode with the local model. This takes about a minute.</span></div>`;
      if (episode)
        content += `<article class="story-episode"><h3>Night ${e(episode.night)}</h3>${episode.text
          .split(/\n\s*\n/)
          .map((p) => `<p>${e(p.trim())}</p>`)
          .join("")}</article>`;
    }
    const actions = story
      ? `<label class="checkbox story-sleep"><input id="story-sleep" type="checkbox" checked>Sleep afterwards</label>${button("stop", "Stop speaking", "ghost", !speech || !["speaking", "synthesizing"].includes(speech.state))}${button("tell", "Tell tonight's episode", "primary", writing)}`
      : button("start", "Start a story", "primary");
    return panel("Tonight", content, actions);
  }

  function continuity() {
    const story = data?.story;
    if (!story) return "";
    const cast = story.cast
      .map(
        (c) =>
          `<tr><td><strong>${e(c.name)}</strong>${c.name === story.protagonist ? ' <small class="accent">Main character</small>' : ""}</td><td>${e(c.role)}</td><td class="muted">${e(c.description)}</td></tr>`,
      )
      .join("");
    const departed = story.departed.length
      ? story.departed
          .map(
            (d) =>
              `<tr><td><strong>${e(d.name)}</strong></td><td>${badge(d.reason === "died" ? "Died" : "Left", "neutral")}</td><td class="muted">Night ${e(d.night)}</td></tr>`,
          )
          .join("")
      : `<tr><td colspan="3" class="empty">Nobody has left the story.</td></tr>`;
    const changes = state.storyChanges?.length
      ? `<div class="notice">Last night: ${e(state.storyChanges.join("; "))}</div>`
      : "";
    return (
      panel(
        "Current state",
        `${changes}<div class="table-scroll"><table><thead><tr><th>CAST</th><th>ROLE</th><th>DESCRIPTION</th></tr></thead><tbody>${cast}</tbody></table></div><div class="table-scroll"><table><thead><tr><th>DEPARTED</th><th>REASON</th><th>WHEN</th></tr></thead><tbody>${departed}</tbody></table></div>`,
        can("robot:control") ? button("start", "Start a new story") : "",
      ) +
      panel(
        "Story reference",
        row("Genre", e(story.genre || "Not set")) +
          row("Premise", e(story.premise)) +
          row("The story so far", e(story.summary || "Nothing yet.")) +
          row("Current situation", e(story.situation || "The story begins.")),
      )
    );
  }

  function voice() {
    if (!can("pipeline:manage") || !state.pipeline?.config) return "";
    const cfg = state.pipeline.config.speech;
    const active = state.pipeline.active_config?.speech || cfg;
    const pending = JSON.stringify(cfg) !== JSON.stringify(active);
    return panel(
      "Voice",
      row("Engine", e(engines[cfg.tts] || cfg.tts)) +
        (cfg.tts === "piper"
          ? row("Piper voice", e(cfg.tts_voice || "Not set"))
          : "") +
        (cfg.tts === "elevenlabs"
          ? row(
              "ElevenLabs voice",
              `<code>${e(cfg.elevenlabs_voice_id)}</code> · ${e(cfg.elevenlabs_model)}`,
            ) +
            row(
              "API key",
              secrets.elevenlabs
                ? badge("Stored encrypted")
                : badge("Not set", "danger"),
            )
          : "") +
        row("Speaker", e(cfg.output_device || "System default")) +
        (pending
          ? `<div class="notice">Voice settings saved but not active yet.</div>`
          : ""),
      button("voice", "Configure voice"),
    );
  }

  function render() {
    if (!data)
      return panel("Actions", `<div class="panel-note">Loading…</div>`);
    // The voice speaks everything Mirae says, so it stays visible with Story off.
    return actionList() + (storyOn() ? tonight() + continuity() : "") + voice();
  }

  function rerender() {
    if (state.page === "actions") $("#content").innerHTML = render();
  }

  function poll() {
    clearTimeout(timer);
    if (state.page !== "actions") return;
    timer = setTimeout(async () => {
      try {
        const next = await api("/api/speech");
        // Re-render only on change: rebuilding the page would restart the audio player.
        if (JSON.stringify(next) !== JSON.stringify(speech)) {
          speech = next;
          if (!$("#modal").open) rerender();
        }
      } catch {
        // The next poll retries.
      }
      poll();
    }, 1500);
  }

  async function afterRender() {
    if (state.page !== "actions") return clearTimeout(timer);
    if (!data) {
      try {
        await load();
      } catch (error) {
        toast(error.message, true);
        return;
      }
      rerender();
    }
    poll();
  }

  function parseCast(text) {
    return text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [name, role, ...rest] = line.split(/\s+[—–-]\s+/);
        if (!name || !role)
          throw Error(
            `Write each character as "Name — role — description": ${line}`,
          );
        return { name, role, description: rest.join(" - ") };
      });
  }

  function startDialog() {
    dialog(
      "Start a new story",
      `<p class="field-hint">This replaces the current story and its episodes. The first character is the main character and stays in the story.</p><label>Genre<select name="genre">${genres.map((g) => option(g, g, g === "Fantasy")).join("")}</select></label><label>Premise<textarea name="premise" rows="3" required maxlength="1000" placeholder="A small lighthouse island where a keeper and his apprentice look after ships at night."></textarea></label><label>Characters, one per line<textarea name="cast" rows="4" required placeholder="John — lighthouse keeper — old, patient, hums sea shanties&#10;Clay — John's apprentice — young, curious, afraid of storms"></textarea></label>`,
      async (form) => {
        const cast = parseCast(form.get("cast"));
        if (!cast.length) throw Error("Add at least the main character.");
        await api("/api/story", "PUT", {
          premise: form.get("premise").trim(),
          genre: form.get("genre"),
          protagonist: cast[0].name,
          cast,
        });
        data = null;
        lastEpisode = null;
        state.storyChanges = [];
        await saved("New story started.");
      },
      "Start story",
    );
  }

  async function voiceDialog() {
    dialog(
      "Discovering speakers",
      '<progress aria-label="Discovering connected speakers"></progress>',
      null,
    );
    let devices = { outputs: [] };
    try {
      devices = (await api("/api/admin/pipeline/devices/refresh", "POST"))
        .audio;
    } catch (error) {
      toast(error.message, true);
    }
    const cfg = state.pipeline.config.speech;
    const outputs = devices.outputs || [];
    dialog(
      "Configure voice",
      `<label>Engine<select name="tts">${Object.entries(engines)
        .map(([id, label]) => option(id, label, cfg.tts === id))
        .join(
          "",
        )}</select></label><p class="field-hint">Piper runs on the robot with no internet. ElevenLabs sends the story text to ElevenLabs.</p>${field("Piper voice model (.onnx)", "tts_voice", "text", cfg.tts_voice || "", 'placeholder="models/piper/en_GB-jenny_dioco-medium.onnx"')}<div class="form-columns">${field("ElevenLabs voice ID", "elevenlabs_voice_id", "text", cfg.elevenlabs_voice_id, 'required pattern="[A-Za-z0-9]{8,40}"')}${field("ElevenLabs model", "elevenlabs_model", "text", cfg.elevenlabs_model, 'required pattern="[a-z0-9_]{3,40}"')}</div>${field(`ElevenLabs API key${secrets.elevenlabs ? " (stored; leave blank to keep)" : ""}`, "elevenlabs_key", "password", "", 'autocomplete="off"')}${secrets.elevenlabs ? '<label class="checkbox"><input name="clear_key" type="checkbox">Remove the stored ElevenLabs key</label>' : ""}<label>Speaker<select name="output_device">${option("", "System default", cfg.output_device === null)}${outputs
        .map((d) =>
          option(d.id, d.name + " · " + d.host_api, cfg.output_device === d.id),
        )
        .join(
          "",
        )}${cfg.output_device && !outputs.some((d) => d.id === cfg.output_device) ? option(cfg.output_device, cfg.output_device + " (not connected)", true) : ""}</select></label>${devices.error ? `<p class="form-error">${e(devices.error)}</p>` : ""}`,
      async (form) => {
        const tts = form.get("tts");
        const key = form.get("elevenlabs_key");
        if (tts === "elevenlabs" && !key && !secrets.elevenlabs)
          throw Error("Enter an ElevenLabs API key.");
        if (tts === "piper" && !form.get("tts_voice"))
          throw Error("Enter the path of a Piper voice model.");
        if (key || form.has("clear_key"))
          await api("/api/admin/pipeline/secrets/elevenlabs", "PUT", {
            api_key: form.has("clear_key") ? null : key,
          });
        await api("/api/admin/pipeline/config/speech", "PUT", {
          tts,
          tts_voice: form.get("tts_voice") || null,
          elevenlabs_voice_id: form.get("elevenlabs_voice_id"),
          elevenlabs_model: form.get("elevenlabs_model"),
          output_device: form.get("output_device") || null,
        });
        await api("/api/admin/pipeline/local/apply", "POST");
        data = null;
        await saved("Voice settings applied.");
      },
      "Save & apply",
    );
  }

  async function tell() {
    writing = true;
    rerender();
    try {
      const result = await api("/api/story/tell", "POST", {
        sleep: $("#story-sleep")?.checked ?? false,
      });
      lastEpisode = result.episode;
      state.storyChanges = result.changes;
      if (!result.continuity_updated)
        toast(
          "The continuity notes were invalid; the cast is unchanged.",
          true,
        );
      writing = false;
      await load();
    } catch (error) {
      writing = false;
      toast(error.message, true);
    }
    rerender();
  }

  document.addEventListener("click", async (event) => {
    const source = event.target.closest("[data-story]");
    if (!source || state.page !== "actions") return;
    const name = source.dataset.story;
    if (name === "toggle")
      try {
        const action = actions.find((a) => a.id === source.dataset.id);
        ({ actions } = await api("/api/actions/" + action.id, "PUT", {
          enabled: !action.enabled,
        }));
        toast(`${action.name} turned ${action.enabled ? "off" : "on"}.`);
        rerender();
      } catch (error) {
        toast(error.message, true);
      }
    if (name === "tell") await tell();
    if (name === "start") startDialog();
    if (name === "voice") await voiceDialog();
    if (name === "stop")
      try {
        await api("/api/speech/stop", "POST");
      } catch (error) {
        toast(error.message, true);
      }
  });

  return { render, afterRender };
}
