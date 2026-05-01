const state = {
  user: null,
  categories: [],
  subscriptions: [],
  editingId: null,
  authMode: "login",
};

const currencySymbols = {
  PHP: "PHP ",
  USD: "$",
  EUR: "€",
  GBP: "£",
  JPY: "¥",
};

const $ = (id) => document.getElementById(id);

function money(value) {
  const code = state.user?.settings?.currency || "PHP";
  return `${currencySymbols[code] || `${code} `}${Number(value || 0).toFixed(2)}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "same-origin",
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Something went wrong.");
  }
  return data;
}

function toast(message) {
  $("toast").textContent = message;
  $("toast").classList.add("show");
  setTimeout(() => $("toast").classList.remove("show"), 2600);
}

function setAuthMode(mode) {
  state.authMode = mode;
  $("loginTab").classList.toggle("active", mode === "login");
  $("registerTab").classList.toggle("active", mode === "register");
  $("nameField").classList.toggle("hidden", mode === "login");
  $("authSubmit").textContent = mode === "login" ? "Sign in" : "Create account";
  $("authError").textContent = "";
}

function showApp() {
  $("authView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("userName").textContent = state.user.name;
  $("userEmail").textContent = state.user.email;
  $("avatar").textContent = state.user.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function showAuth() {
  $("appView").classList.add("hidden");
  $("authView").classList.remove("hidden");
}

function clearAuthForm() {
  $("authName").value = "";
  $("authEmail").value = "";
  $("authPassword").value = "";
  $("authError").textContent = "";
}

async function loadInitial() {
  const session = await api("/api/session");
  if (!session.user) {
    showAuth();
    return;
  }
  state.user = session.user;
  showApp();
  await refreshAll();
}

async function refreshAll() {
  await loadCategories();
  await loadSubscriptions();
  await loadDashboard();
  loadSettings();
}

async function loadCategories() {
  const data = await api("/api/categories");
  state.categories = data.categories;
  const allOptions = ['<option value="">All categories</option>']
    .concat(state.categories.map((cat) => `<option value="${cat.id}">${escapeHtml(cat.name)}</option>`))
    .join("");
  $("categoryFilter").innerHTML = allOptions;
  $("subCategory").innerHTML = state.categories
    .map((cat) => `<option value="${cat.id}">${escapeHtml(cat.name)}</option>`)
    .join("");
}

async function loadSubscriptions() {
  const params = new URLSearchParams();
  if ($("searchInput").value) params.set("q", $("searchInput").value);
  if ($("categoryFilter").value) params.set("category", $("categoryFilter").value);
  if ($("statusFilter").value) params.set("status", $("statusFilter").value);
  const data = await api(`/api/subscriptions?${params}`);
  state.subscriptions = data.subscriptions;
  renderSubscriptions();
  renderUpcoming();
}

async function loadDashboard() {
  const data = await api("/api/dashboard");
  $("monthlyTotal").textContent = money(data.monthlyTotal);
  $("annualTotal").textContent = money(data.annualTotal);
  $("activeCount").textContent = data.activeCount;
  $("renewingCount").textContent = data.renewingSoonCount;
  renderCategoryChart(data.categoryTotals);
  renderReminders(data.reminders);
  renderReportSummary(data);
}

function renderSubscriptions() {
  const body = $("subscriptionsBody");
  if (!state.subscriptions.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No subscriptions found.</td></tr>`;
    return;
  }
  body.innerHTML = state.subscriptions.map((sub) => `
    <tr>
      <td><strong>${escapeHtml(sub.name)}</strong><br><small>${escapeHtml(sub.notes || "")}</small></td>
      <td><span class="badge">${escapeHtml(sub.categoryName)}</span></td>
      <td>${capitalize(sub.cycle)}</td>
      <td class="status-${sub.status}">${formatDate(sub.renewalDate)}<br><small>${renewalText(sub)}</small></td>
      <td>${money(sub.cost)}</td>
      <td>
        <div class="row-actions">
          <button class="ghost icon-btn" onclick="editSubscription('${sub.id}')">Edit</button>
          <button class="ghost icon-btn" onclick="deleteSubscription('${sub.id}')">Delete</button>
        </div>
      </td>
    </tr>
  `).join("");
}

function renderUpcoming() {
  const sorted = [...state.subscriptions].sort((a, b) => a.daysUntilRenewal - b.daysUntilRenewal);
  $("upcomingList").innerHTML = sorted.length
    ? sorted.map((sub) => `
      <article class="list-card">
        <div>
          <strong>${escapeHtml(sub.name)}</strong>
          <small>${escapeHtml(sub.categoryName)} · ${formatDate(sub.renewalDate)} · ${renewalText(sub)}</small>
        </div>
        <strong>${money(sub.cost)}</strong>
      </article>
    `).join("")
    : `<div class="empty">Add subscriptions to see your renewal calendar.</div>`;
}

function renderCategoryChart(totals) {
  const entries = Object.entries(totals);
  if (!entries.length) {
    $("categoryChart").innerHTML = `<div class="empty">No spending data yet.</div>`;
    return;
  }
  const max = Math.max(...entries.map(([, value]) => value));
  $("categoryChart").innerHTML = entries.map(([name, value]) => `
    <div class="bar-row">
      <strong>${escapeHtml(name)}</strong>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(6, (value / max) * 100)}%"></div></div>
      <span>${money(value)}</span>
    </div>
  `).join("");
}

function renderReminders(reminders) {
  $("reminderList").innerHTML = reminders.length
    ? reminders.map((reminder) => `
      <article class="list-card">
        <div>
          <strong>${escapeHtml(reminder.name)}</strong>
          <small>${escapeHtml(reminder.message)} Renewal: ${formatDate(reminder.renewalDate)}</small>
        </div>
      </article>
    `).join("")
    : `<div class="empty">No reminder notifications are due today.</div>`;
}

function renderReportSummary(data) {
  $("reportSummary").innerHTML = `
    <div><span>Monthly total</span><strong>${money(data.monthlyTotal)}</strong></div>
    <div><span>Annual total</span><strong>${money(data.annualTotal)}</strong></div>
    <div><span>Active subscriptions</span><strong>${data.activeCount}</strong></div>
    <div><span>Renewing soon</span><strong>${data.renewingSoonCount}</strong></div>
  `;
}

function loadSettings() {
  $("profileName").value = state.user.name;
  $("profileEmail").value = state.user.email;
  $("currencySelect").value = state.user.settings.currency || "PHP";
  $("remindSevenDays").checked = state.user.settings.remindSevenDays !== false;
  $("remindOneDay").checked = state.user.settings.remindOneDay !== false;
}

function openSubscriptionModal(sub = null) {
  state.editingId = sub?.id || null;
  $("modalTitle").textContent = sub ? "Edit subscription" : "Add subscription";
  $("subName").value = sub?.name || "";
  $("subCost").value = sub?.cost || "";
  $("subCycle").value = sub?.cycle || "monthly";
  $("subCategory").value = sub?.categoryId || "streaming";
  $("subRenewal").value = sub?.renewalDate || "";
  $("subNotes").value = sub?.notes || "";
  $("subError").textContent = "";
  $("subscriptionModal").classList.remove("hidden");
}

function closeSubscriptionModal() {
  $("subscriptionModal").classList.add("hidden");
  state.editingId = null;
}

function editSubscription(id) {
  const sub = state.subscriptions.find((item) => item.id === id);
  if (sub) openSubscriptionModal(sub);
}

async function deleteSubscription(id) {
  if (!confirm("Delete this subscription?")) return;
  await api(`/api/subscriptions/${id}`, { method: "DELETE" });
  toast("Subscription deleted.");
  await loadSubscriptions();
  await loadDashboard();
}

async function saveSubscription(event) {
  event.preventDefault();
  const payload = {
    name: $("subName").value,
    cost: $("subCost").value,
    cycle: $("subCycle").value,
    categoryId: $("subCategory").value,
    renewalDate: $("subRenewal").value,
    notes: $("subNotes").value,
  };
  try {
    const path = state.editingId ? `/api/subscriptions/${state.editingId}` : "/api/subscriptions";
    const method = state.editingId ? "PUT" : "POST";
    await api(path, { method, body: JSON.stringify(payload) });
    closeSubscriptionModal();
    toast("Subscription saved.");
    await loadSubscriptions();
    await loadDashboard();
  } catch (error) {
    $("subError").textContent = error.message;
  }
}

async function saveSettings() {
  const settings = {
    currency: $("currencySelect").value,
    remindSevenDays: $("remindSevenDays").checked,
    remindOneDay: $("remindOneDay").checked,
  };
  const data = await api("/api/profile", {
    method: "PUT",
    body: JSON.stringify({ name: $("profileName").value, settings }),
  });
  state.user = data.user;
  showApp();
  toast("Settings saved.");
  await refreshAll();
}

async function addCategory() {
  const name = $("newCategory").value.trim();
  if (!name) return;
  await api("/api/categories", { method: "POST", body: JSON.stringify({ name }) });
  $("newCategory").value = "";
  toast("Category added.");
  await loadCategories();
}

function switchPage(pageName) {
  document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
  document.querySelectorAll(".nav-link").forEach((link) => link.classList.remove("active"));
  $(`${pageName}Page`).classList.add("active");
  document.querySelector(`[data-page="${pageName}"]`).classList.add("active");
  if (pageName === "dashboard" || pageName === "reports") loadDashboard();
  if (pageName === "upcoming") loadSubscriptions();
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function renewalText(sub) {
  if (sub.daysUntilRenewal < 0) return `${Math.abs(sub.daysUntilRenewal)} day(s) overdue`;
  if (sub.daysUntilRenewal === 0) return "renews today";
  return `${sub.daysUntilRenewal} day(s) left`;
}

function capitalize(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value || "";
  return div.innerHTML;
}

$("loginTab").addEventListener("click", () => setAuthMode("login"));
$("registerTab").addEventListener("click", () => setAuthMode("register"));

$("authForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("authError").textContent = "";
  const payload = {
    name: $("authName").value,
    email: $("authEmail").value,
    password: $("authPassword").value,
  };
  try {
    const data = await api(state.authMode === "login" ? "/api/login" : "/api/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.user = data.user;
    clearAuthForm();
    showApp();
    if (state.authMode === "register") {
      toast(data.welcomeEmailSent ? "Welcome email sent." : data.emailWarning || "Welcome email could not be sent.");
    }
    await refreshAll();
  } catch (error) {
    $("authError").textContent = error.message;
  }
});

$("logoutBtn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  state.user = null;
  showAuth();
});

document.querySelectorAll(".nav-link").forEach((button) => {
  button.addEventListener("click", () => switchPage(button.dataset.page));
});

$("addSubBtn").addEventListener("click", () => openSubscriptionModal());
$("cancelSubBtn").addEventListener("click", closeSubscriptionModal);
$("subscriptionModal").addEventListener("click", (event) => {
  if (event.target === $("subscriptionModal")) closeSubscriptionModal();
});
$("subscriptionForm").addEventListener("submit", saveSubscription);
$("searchInput").addEventListener("input", loadSubscriptions);
$("categoryFilter").addEventListener("change", loadSubscriptions);
$("statusFilter").addEventListener("change", loadSubscriptions);
$("saveSettingsBtn").addEventListener("click", saveSettings);
$("addCategoryBtn").addEventListener("click", addCategory);
$("sendRemindersBtn").addEventListener("click", async () => {
  try {
    const result = await api("/api/reminders/send", { method: "POST" });
    toast(result.message);
    await loadDashboard();
  } catch (error) {
    toast(error.message);
  }
});

setAuthMode("login");
loadInitial().catch((error) => {
  console.error(error);
  toast(error.message);
});
