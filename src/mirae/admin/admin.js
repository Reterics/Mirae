import { createPipelineUI } from "./pipeline-ui.js";
import { createStoryUI } from "./story-ui.js";
const $ = (selector) => document.querySelector(selector);
const state = {
  user: null,
  csrf: "",
  users: [],
  roles: [],
  tokens: [],
  audit: [],
  permissions: {},
  runtime: null,
  page: "overview",
  registration: false,
  pipeline: null,
  connections: [],
  schema: {},
};
const pages = {
  overview: ["Runtime", "", null],
  actions: ["Actions", "", null],
  connections: ["LLM connections", "", "Add connection"],
  local: ["Local processing", "", null],
  hardware: ["Hardware", "", null],
  users: ["Users", "", "Add user"],
  roles: ["Roles & permissions", "", "Create role"],
  tokens: ["API keys", "", "Create API key"],
  audit: ["Audit log", "", null],
};
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const can = (permission) => state.user?.permissions.includes(permission);
const date = (value) =>
  value
    ? new Date(value * 1000).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Never";
const roleName = (id) =>
  state.roles.find((r) => r.id === id)?.name || state.user?.role_name || id;
const badge = (label, variant = "") =>
  `<span class="badge ${variant}">${escape(label)}</span>`;
const action = (name, id, label, disabled = false) =>
  `<button class="button small ghost" data-action="${name}" data-id="${escape(id)}" ${disabled ? "disabled" : ""}>${escape(label)}</button>`;
const pipelineUI = createPipelineUI({
  state,
  api,
  escape,
  badge,
  action,
  date,
  field,
  dialog,
  saved,
  toast,
  reload,
  navigate,
  can,
});
const storyUI = createStoryUI({
  state,
  api,
  escape,
  badge,
  field,
  dialog,
  saved,
  toast,
  can,
});
let toastTimer;
const drawer = $("#navigation-drawer");
const navigationToggle = $("#navigation-toggle");
const mobileNavigation = window.matchMedia("(max-width: 800px)");
function closeNavigation() {
  if (drawer.open) drawer.close();
  navigationToggle.setAttribute("aria-expanded", "false");
}
function placeNavigation() {
  const hadFocus = $("#sidebar").contains(document.activeElement);
  closeNavigation();
  if (mobileNavigation.matches) {
    drawer.append($("#sidebar"));
    if (hadFocus && !$("#shell").hidden) navigationToggle.focus();
  } else {
    $("#shell").prepend($("#sidebar"));
    if (hadFocus && !$("#shell").hidden) $("#navigation .active")?.focus();
  }
}
navigationToggle.addEventListener("click", () => {
  if (!mobileNavigation.matches || drawer.open) return;
  drawer.showModal();
  navigationToggle.setAttribute("aria-expanded", "true");
  $("#navigation .active")?.focus();
});
$("#navigation-close").addEventListener("click", closeNavigation);
drawer.addEventListener("close", () => {
  navigationToggle.setAttribute("aria-expanded", "false");
});
drawer.addEventListener("click", (event) => {
  const bounds = drawer.getBoundingClientRect();
  if (
    event.target === drawer &&
    (event.clientX < bounds.left ||
      event.clientX > bounds.right ||
      event.clientY < bounds.top ||
      event.clientY > bounds.bottom)
  )
    closeNavigation();
});
mobileNavigation.addEventListener("change", placeNavigation);
placeNavigation();
function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast${error ? " error" : ""}`;
  element.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    element.hidden = true;
  }, 5000);
}
async function api(path, method = "GET", data) {
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(state.csrf ? { "X-CSRF-Token": state.csrf } : {}),
    },
    ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && state.user && !path.endsWith("/password")) {
      state.user = null;
      await showAuth();
    }
    const message = Array.isArray(body.detail)
      ? body.detail.map((e) => `${e.loc.at(-1)}: ${e.msg}`).join("; ")
      : body.detail || "Request failed. Please try again.";
    throw new Error(message);
  }
  return body;
}
async function showAuth() {
  closeNavigation();
  $("#shell").hidden = true;
  $("#loading").hidden = true;
  $("#auth").hidden = false;
  state.csrf = "";
  $("#modal").close();
  try {
    state.registration = (await api("/api/auth/status")).registration_open;
  } catch (error) {
    $("#auth-error").textContent = error.message;
    return;
  }
  $("#auth-title").textContent = state.registration
    ? "Create administrator"
    : "Sign in to Mirae";
  $("#auth-description").textContent = state.registration
    ? "Registration closes after the first administrator is created."
    : "Enter your account credentials.";
  $("#display-name-label").hidden = !state.registration;
  $('[name="display_name"]').required = state.registration;
  const password = $('#auth-form [name="password"]');
  password.minLength = state.registration ? 12 : 1;
  password.autocomplete = state.registration
    ? "new-password"
    : "current-password";
  password.value = "";
  $("#password-hint").hidden = !state.registration;
  $("#auth-submit").textContent = state.registration
    ? "Create administrator"
    : "Sign in";
  $("#auth-note").textContent = state.registration
    ? "Registration closes automatically after this account is created."
    : "Accounts are provisioned by your administrator.";
}
$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = $("#auth-submit");
  submit.disabled = true;
  $("#auth-error").textContent = "";
  const values = Object.fromEntries(new FormData(event.target));
  if (!state.registration) delete values.display_name;
  try {
    const result = await api(
      `/api/auth/${state.registration ? "register" : "login"}`,
      "POST",
      values,
    );
    state.user = result.user;
    state.csrf = result.csrf_token;
    event.target.reset();
    await enter();
  } catch (error) {
    $("#auth-error").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
function identity() {
  $("#account-name").textContent = state.user.display_name;
  $("#account-role").textContent = roleName(state.user.role_id);
  $("#avatar").textContent = state.user.display_name.slice(0, 2).toUpperCase();
  document.querySelectorAll("[data-permission]").forEach((element) => {
    element.hidden = !can(element.dataset.permission);
  });
}
async function enter() {
  $("#auth").hidden = true;
  $("#loading").hidden = true;
  $("#shell").hidden = false;
  await reload();
  identity();
  navigate(location.hash.slice(1) || "overview");
}
async function reload() {
  const management = ["users:manage", "roles:manage", "tokens:manage"].some(
    can,
  );
  const [
    users,
    roles,
    tokens,
    audit,
    permissions,
    pipeline,
    connections,
    schema,
  ] = await Promise.all([
    management ? api("/api/admin/users") : [],
    management ? api("/api/admin/roles") : [],
    can("tokens:manage") ? api("/api/admin/tokens") : [],
    can("audit:read") ? api("/api/admin/audit") : [],
    api("/api/admin/permissions"),
    can("pipeline:manage")
      ? api("/api/admin/pipeline").catch((error) => ({ error: error.message }))
      : null,
    can("pipeline:manage") ? api("/api/admin/pipeline/connections") : [],
    can("pipeline:manage") ? api("/api/admin/pipeline/schema") : {},
  ]);
  Object.assign(state, {
    users,
    roles,
    tokens,
    audit,
    permissions,
    pipeline,
    connections,
    schema,
  });
  $("#users-count").textContent = users.length;
  identity();
  await refreshRuntime();
}
async function refreshRuntime() {
  if (!can("robot:read")) {
    state.runtime = null;
    $("#connection").textContent = "Telemetry restricted";
    $("#connection").className = "connection";
    return;
  }
  try {
    state.runtime = await api("/api/status");
    const healthy = state.runtime.runtime?.healthy;
    $("#connection").className = `connection${healthy ? "" : " offline"}`;
    $("#connection").replaceChildren(
      Object.assign(document.createElement("span"), {
        className: "status-dot",
      }),
      document.createTextNode(healthy ? "Runtime online" : "Runtime fault"),
    );
    $("#backend-label").textContent = state.pipeline?.host || "";
    $("#updated-at").textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    $("#connection").textContent = "Runtime unavailable";
    $("#connection").className = "connection offline";
  }
}
function navigate(page) {
  const permission = {
    connections: "pipeline:manage",
    local: "pipeline:manage",
    hardware: "pipeline:manage",
    users: "users:manage",
    roles: "roles:manage",
    tokens: "tokens:manage",
    audit: "audit:read",
  }[page];
  state.page =
    pages[page] && (!permission || can(permission)) ? page : "overview";
  const [title, description, create] = pages[state.page];
  $("#page-title").textContent = title;
  $("#page-description").textContent = description;
  $("#create-button").hidden = !create;
  $("#create-button").textContent = `+ ${create}`;
  document.querySelectorAll("[data-page]").forEach((button) => {
    const active = button.dataset.page === state.page;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  render();
}
$("#navigation").addEventListener("click", (event) => {
  const button = event.target.closest("[data-page]");
  if (button) {
    const mobile = drawer.open;
    closeNavigation();
    location.hash = button.dataset.page;
    if (mobile) $("#page-title").focus();
  }
});
$(".wordmark").addEventListener("click", () => {
  const mobile = drawer.open;
  closeNavigation();
  if (mobile) $("#page-title").focus();
});
window.addEventListener("hashchange", () => {
  if (state.user) navigate(location.hash.slice(1));
});
function table(title, headers, rows, count, placeholder) {
  return `<div class="panel"><div class="panel-heading"><h2>${title}</h2><small>${count} records</small></div><div class="toolbar"><input id="table-search" type="search" aria-label="Search ${title}" placeholder="Search ${title.toLowerCase()}…"><select id="table-filter" aria-label="Filter records"><option value="">All records</option><option value="active">Active</option><option value="inactive">Inactive</option></select></div><div class="table-scroll"><table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows || `<tr><td colspan="${headers.length}" class="empty"><strong>${placeholder}</strong></td></tr>`}</tbody></table></div><div class="table-caption"><span id="table-caption">${count} records</span></div></div>`;
}
function overview() {
  return pipelineUI.overview();
}
function render() {
  let html = pipelineUI.render(state.page);
  if (state.page === "overview") html = overview();
  if (state.page === "actions") html = storyUI.render();
  if (state.page === "users")
    html = table(
      "Users",
      ["USER", "ROLE", "STATUS", "LAST SIGN-IN", "CREATED", ""],
      state.users
        .map(
          (u) =>
            `<tr data-search="${escape(`${u.display_name} ${u.username} ${roleName(u.role_id)}`.toLowerCase())}" data-status="${u.active ? "active" : "inactive"}"><td><div class="person"><span class="avatar">${escape(u.display_name.slice(0, 2).toUpperCase())}</span><span><strong>${escape(u.display_name)} ${u.id === state.user.id ? '<small class="accent">You</small>' : ""}</strong><small>@${escape(u.username)}</small></span></div></td><td>${badge(roleName(u.role_id), "role")}</td><td>${badge(u.active ? "Active" : "Disabled", u.active ? "" : "neutral")}</td><td class="muted">${date(u.last_login)}</td><td class="muted">${date(u.created_at)}</td><td><div class="row-actions">${action("edit-user", u.id, "Edit")}${action("reset-user", u.id, "Password")}${action("delete-user", u.id, "Delete")}</div></td></tr>`,
        )
        .join(""),
      state.users.length,
      "No users found",
    );
  if (state.page === "roles")
    html = table(
      "Access roles",
      ["ROLE", "PERMISSIONS", "MEMBERS", "TYPE", ""],
      state.roles
        .map(
          (r) =>
            `<tr data-search="${escape(`${r.name} ${r.permissions.join(" ")}`.toLowerCase())}" data-status="active"><td><strong>${escape(r.name)}</strong></td><td><div class="scope-list">${r.permissions.map((p) => `<code>${escape(p)}</code>`).join("") || '<span class="muted">No permissions</span>'}</div></td><td>${r.members}</td><td>${badge(r.builtin ? "Built-in" : "Custom", "neutral")}</td><td><div class="row-actions">${action("edit-role", r.id, r.builtin ? "Inspect" : "Edit")}${!r.builtin ? action("delete-role", r.id, "Delete", r.members > 0) : ""}</div></td></tr>`,
        )
        .join(""),
      state.roles.length,
      "No custom roles yet",
    );
  if (state.page === "tokens")
    html = table(
      "API credentials",
      ["KEY", "OWNER", "SCOPES", "STATUS", "LAST USED", "EXPIRES", ""],
      state.tokens
        .map((t) => {
          const active = !t.revoked_at && t.expires_at * 1000 > Date.now();
          return `<tr data-search="${escape(`${t.name} ${t.username} ${t.prefix}`.toLowerCase())}" data-status="${active ? "active" : "inactive"}"><td><div class="person"><span><strong>${escape(t.name)}</strong><small><code>${escape(t.prefix)}••••</code></small></span></div></td><td class="muted">@${escape(t.username)}</td><td><div class="scope-list">${t.scopes.map((p) => `<code>${escape(p)}</code>`).join("")}</div></td><td>${badge(t.revoked_at ? "Revoked" : active ? "Active" : "Expired", active ? "" : "neutral")}</td><td class="muted">${date(t.last_used)}</td><td class="muted">${date(t.expires_at)}</td><td>${active ? action("revoke-token", t.id, "Revoke") : ""}</td></tr>`;
        })
        .join(""),
      state.tokens.length,
      "No API keys created",
    );
  if (state.page === "audit")
    html = table(
      "Access audit log",
      ["TIMESTAMP", "ACTOR", "EVENT", "TARGET"],
      state.audit
        .map(
          (a) =>
            `<tr data-search="${escape(`${a.actor} ${a.action} ${a.target}`.toLowerCase())}" data-status="active"><td class="muted">${date(a.at)}</td><td>@${escape(a.actor)}</td><td><code>${escape(a.action)}</code></td><td>${escape(a.target)}</td></tr>`,
        )
        .join(""),
      state.audit.length,
      "No access events yet",
    );
  $("#content").innerHTML = html;
  pipelineUI.afterRender();
  storyUI.afterRender();
  $("#table-search")?.addEventListener("input", filterTable);
  $("#table-filter")?.addEventListener("change", filterTable);
}
function filterTable() {
  const search = $("#table-search").value.toLowerCase();
  const status = $("#table-filter").value;
  let count = 0;
  document.querySelectorAll("tr[data-search]").forEach((row) => {
    row.hidden =
      !row.dataset.search.includes(search) ||
      (status && row.dataset.status !== status);
    if (!row.hidden) count++;
  });
  $("#table-caption").textContent = `${count} matching records`;
}
function field(label, name, type = "text", value = "", extra = "") {
  return `<label>${label}<input name="${name}" type="${type}" value="${escape(value)}" ${extra}></label>`;
}
function roleSelect(id = "viewer") {
  return `<label>Role<select name="role_id">${state.roles.map((r) => `<option value="${r.id}" ${r.id === id ? "selected" : ""}>${escape(r.name)}</option>`).join("")}</select></label>`;
}
function permissionChecks(
  selected = [],
  allowed = Object.keys(state.permissions),
  disabled = false,
) {
  return Object.entries(state.permissions)
    .filter(([id]) => allowed.includes(id))
    .map(
      ([id, description]) =>
        `<label class="checkbox"><input type="checkbox" name="permissions" value="${id}" ${selected.includes(id) ? "checked" : ""} ${disabled ? "disabled" : ""}><span><code>${id}</code><small>${escape(description)}</small></span></label>`,
    )
    .join("");
}
function dialog(
  title,
  content,
  onSubmit,
  label = "Save changes",
  danger = false,
) {
  $("#modal-body").innerHTML =
    `<form id="modal-form"><div class="modal-heading"><h2 id="modal-title">${escape(title)}</h2><button type="button" class="button icon" data-close aria-label="Close dialog">×</button></div><div class="modal-content"><div class="form-grid">${content}</div><p id="modal-error" class="form-error" role="alert"></p></div><div class="modal-actions"><button type="button" class="button ghost" data-close>Cancel</button>${onSubmit ? `<button class="button ${danger ? "danger" : "primary"}" type="submit">${label}</button>` : ""}</div></form>`;
  $("#modal").showModal();
  if (onSubmit)
    $("#modal-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const button =
        event.submitter || event.target.querySelector('[type="submit"]');
      button.disabled = true;
      $("#modal-error").textContent = "";
      try {
        await onSubmit(new FormData(event.target));
      } catch (error) {
        if ($("#modal-error")) $("#modal-error").textContent = error.message;
        else toast(error.message, true);
      } finally {
        if (button.isConnected) button.disabled = false;
      }
    });
}
$("#modal").addEventListener("click", (event) => {
  if (event.target.closest("[data-close]")) $("#modal").close();
});
$("#modal").addEventListener("close", () => {
  if (!$("#modal").open) $("#modal-body").replaceChildren();
});
async function saved(message) {
  $("#modal").close();
  toast(message);
  await reload();
  navigate(state.page);
}
function userDialog(user) {
  const content = user
    ? `${field("Display name", "display_name", "text", user.display_name, 'required maxlength="80"')}${roleSelect(user.role_id)}<label class="checkbox"><input name="active" type="checkbox" ${user.active ? "checked" : ""}>Account active</label>`
    : `${field("Display name", "display_name", "text", "", 'required maxlength="80"')}${field("Username", "username", "text", "", 'required minlength="3" maxlength="64" pattern="[a-zA-Z0-9]([a-zA-Z0-9_.]|-){2,63}" autocomplete="off"')}${field("Initial password", "password", "password", "", 'required minlength="12" maxlength="128" autocomplete="new-password"')}<p class="field-hint">At least 12 characters. Share through a secure channel.</p>${roleSelect()}`;
  dialog(
    user ? `Edit ${user.username}` : "Add user",
    content,
    async (form) => {
      const data = Object.fromEntries(form);
      if (user) data.active = form.has("active");
      await api(
        `/api/admin/users${user ? `/${user.id}` : ""}`,
        user ? "PATCH" : "POST",
        data,
      );
      await saved(user ? "User updated" : "User created");
    },
    user ? "Save changes" : "Create user",
  );
}
function roleDialog(role) {
  const builtin = role?.builtin;
  dialog(
    builtin ? role.name : role ? "Edit role" : "Create access role",
    `${field("Role name", "name", "text", role?.name || "", `required maxlength="80" ${builtin ? "disabled" : ""}`)}<div><span class="eyebrow">PERMISSIONS</span>${permissionChecks(role?.permissions, undefined, builtin)}</div>${builtin ? '<p class="field-hint">Built-in roles are protected. Create a custom role to define a different permission set.</p>' : ""}`,
    builtin
      ? null
      : async (form) => {
          await api(
            `/api/admin/roles${role ? `/${role.id}` : ""}`,
            role ? "PUT" : "POST",
            { name: form.get("name"), permissions: form.getAll("permissions") },
          );
          await saved("Role saved");
        },
  );
}
function tokenDialog() {
  const owners = state.users.filter((u) => u.active);
  const current = owners.find((u) => u.id === state.user.id) || owners[0];
  dialog(
    "Create API key",
    `${field("Key name", "name", "text", "", 'required maxlength="80" ')}<label>Owner<select name="user_id" id="token-owner">${owners.map((u) => `<option value="${u.id}" ${u.id === current?.id ? "selected" : ""}>${escape(u.display_name)} (@${escape(u.username)})</option>`).join("")}</select></label><label>Expires after<select name="expires_days"><option value="7">7 days</option><option value="30" selected>30 days</option><option value="90">90 days</option><option value="365">365 days</option></select></label><div><span class="eyebrow">PERMISSION SCOPES</span><div id="token-scopes"></div></div><p class="field-hint">Permissions cannot exceed those of the owner or issuer. The secret is displayed once.</p>`,
    async (form) => {
      const result = await api("/api/admin/tokens", "POST", {
        name: form.get("name"),
        user_id: form.get("user_id"),
        expires_days: Number(form.get("expires_days")),
        scopes: form.getAll("permissions"),
      });
      $("#modal").close();
      await reload();
      navigate("tokens");
      dialog(
        "API key created",
        `<p>Copy this secret now. It cannot be retrieved again.</p><code class="secret" id="token-secret">${escape(result.secret)}</code><button type="button" id="copy-secret" class="button ghost">Copy key</button><p class="field-hint">Send as Authorization: Bearer &lt;key&gt;. Store it in your integration’s credential store.</p>`,
        null,
      );
      $("#copy-secret").addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(result.secret);
          toast("API key copied");
        } catch {
          toast("Select and copy the key above.", true);
        }
      });
    },
    "Create key",
  );
  const scopes = () => {
    const owner = state.users.find((u) => u.id === $("#token-owner").value);
    const allowed = (
      state.roles.find((r) => r.id === owner?.role_id)?.permissions || []
    ).filter(can);
    $("#token-scopes").innerHTML = permissionChecks(["robot:read"], allowed);
  };
  $("#token-owner").addEventListener("change", scopes);
  scopes();
}
$("#create-button").addEventListener("click", () => {
  if (state.page === "connections") pipelineUI.connectionDialog();
  if (state.page === "users") userDialog();
  if (state.page === "roles") roleDialog();
  if (state.page === "tokens") tokenDialog();
});
$("#content").addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const id = button.dataset.id;
  const name = button.dataset.action;
  const user = state.users.find((u) => u.id === id);
  const role = state.roles.find((r) => r.id === id);
  const token = state.tokens.find((t) => t.id === id);
  if (name === "edit-user") userDialog(user);
  if (name === "edit-role") roleDialog(role);
  if (name === "reset-user")
    dialog(
      `Reset ${user.username}'s password`,
      `${field("New password", "password", "password", "", 'required minlength="12" maxlength="128" autocomplete="new-password"')}<p class="field-hint">Resets revoke all of this user’s sessions and API keys.</p>`,
      async (form) => {
        await api(`/api/admin/users/${id}`, "PATCH", {
          password: form.get("password"),
        });
        await saved("Password reset; credentials revoked");
      },
      "Reset password",
    );
  if (name.startsWith("delete-") || name === "revoke-token") {
    const resource =
      name === "delete-user"
        ? "users"
        : name === "delete-role"
          ? "roles"
          : "tokens";
    const label = user?.username || role?.name || token?.name;
    dialog(
      `${resource === "tokens" ? "Revoke API key" : "Delete " + resource.slice(0, -1)}?`,
      `<p>This withdraws access for <strong>${escape(label)}</strong>. This action cannot be undone.</p>`,
      async () => {
        await api(`/api/admin/${resource}/${id}`, "DELETE");
        await saved("Access record removed");
      },
      resource === "tokens" ? "Revoke key" : "Delete",
      true,
    );
  }
});
$("#account-top").addEventListener("click", () => $("#account-button").click());
$("#account-button").addEventListener("click", () => {
  closeNavigation();
  dialog(
    "Change your password",
    `${field("Current password", "current_password", "password", "", 'required autocomplete="current-password"')}${field("New password", "password", "password", "", 'required minlength="12" maxlength="128" autocomplete="new-password"')}<p class="field-hint">Changing your password signs out every session and revokes your API keys.</p>`,
    async (form) => {
      await api("/api/auth/password", "POST", Object.fromEntries(form));
      state.user = null;
      await showAuth();
      toast("Password changed. Sign in again.");
    },
    "Change password",
  );
});
$("#logout").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", "POST");
    state.user = null;
    await showAuth();
  } catch (error) {
    toast(error.message, true);
  }
});
let refreshing = false;
setInterval(async () => {
  if (!state.user || document.hidden || refreshing || $("#modal").open) return;
  refreshing = true;
  try {
    const session = await api("/api/auth/me");
    const changed =
      JSON.stringify(state.user.permissions) !==
      JSON.stringify(session.user.permissions);
    state.user = session.user;
    state.csrf = session.csrf_token;
    identity();
    await refreshRuntime();
    if (can("pipeline:manage"))
      state.pipeline = await api("/api/admin/pipeline");
    if (changed) navigate(state.page);
    else if (["overview", "local", "hardware"].includes(state.page)) render();
  } catch (error) {
    if (state.user) toast(error.message, true);
  } finally {
    refreshing = false;
  }
}, 5000);
try {
  const session = await api("/api/auth/me");
  state.user = session.user;
  state.csrf = session.csrf_token;
  await enter();
} catch {
  await showAuth();
}
