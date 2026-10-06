const $ = (sel) => document.querySelector(sel);
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const money = (cents) => brl.format(cents / 100);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const icon = (name) => `<svg><use href="#i-${name}"/></svg>`;
const parseISO = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const fmtShort = (iso) => (iso ? parseISO(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(".", "") : "");

const CATEGORY_COLORS = {
  "Mercado": "#0f766e", "Alimentação": "#ea580c", "Moradia": "#b45309", "Contas de consumo": "#0284c7",
  "Transporte": "#4f46e5", "Saúde": "#db2777", "Educação": "#7c3aed", "Lazer": "#65a30d",
  "Compras": "#c026d3", "Serviços e assinaturas": "#0891b2", "Impostos e taxas": "#dc2626",
  "Transferências": "#64748b", "Salário": "#15803d", "Vendas e serviços prestados": "#059669",
  "Rendimentos": "#ca8a04", "Reembolsos": "#0d9488",
};
const PALETTE = Object.values(CATEGORY_COLORS);
const OTHER = "#78716c";

let categories = { expense: [], income: [] };
let transactions = [];
let filter = "all";
let editing = null;

function colorFor(category) {
  if (!category || category.startsWith("Outr")) return OTHER;
  if (CATEGORY_COLORS[category]) return CATEGORY_COLORS[category];
  let h = 0;
  for (const ch of category) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new Error(typeof detail === "string" ? detail : detail.map?.((d) => d.msg).join("; ") ?? JSON.stringify(detail));
  }
  return res.status === 204 ? null : res.json();
}
const jsonBody = (method, data) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

/* --- mês ---------------------------------------------------------------- */

const currentMonth = () => $("#month").value;
function renderMonthLabel() {
  const [y, m] = currentMonth().split("-").map(Number);
  const label = new Date(y, m - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  $("#month-text").textContent = label.charAt(0).toUpperCase() + label.slice(1);
}
function shiftMonth(delta) {
  const [y, m] = currentMonth().split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  $("#month").value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  renderMonthLabel();
  refresh();
}

/* --- resumo ------------------------------------------------------------- */

async function loadSummary() {
  const s = await api(`/api/summary?month=${currentMonth()}`);
  const balance = $("#s-balance");
  balance.textContent = money(s.balance_cents);
  balance.classList.toggle("negative", s.balance_cents < 0);
  $("#s-income").textContent = money(s.income_cents);
  $("#s-expense").textContent = money(s.expense_cents);
  $("#s-pending").textContent = money(s.pending_expense_cents);
  $("#s-receivable").textContent = money(s.pending_income_cents);
  $("#s-review").textContent = String(s.to_review);

  const flow = s.income_cents + s.expense_cents;
  $("#flow-in").style.width = flow ? `${(s.income_cents / flow) * 100}%` : "0";
  $("#flow-out").style.width = flow ? `${(s.expense_cents / flow) * 100}%` : "0";

  const alerts = [];
  if (s.overdue.length) {
    const total = s.overdue.reduce((acc, t) => acc + t.amount_cents, 0);
    alerts.push(`<div class="alert danger">${icon("alert")}<div><b>${s.overdue.length === 1 ? "1 conta vencida" : `${s.overdue.length} contas vencidas`}</b> somando ${money(total)}. Pague ou marque como paga para manter o saldo correto.</div></div>`);
  }
  if (s.to_review) {
    alerts.push(`<div class="alert">${icon("alert")}<div><b>${s.to_review === 1 ? "1 lançamento precisa" : `${s.to_review} lançamentos precisam`} de revisão.</b> Confira valores e descrições lidos automaticamente. <a href="#" data-goto="review" style="color:inherit;font-weight:600">Revisar agora</a></div></div>`);
  }
  $("#alerts").innerHTML = alerts.join("");

  renderCategories(s.by_category.filter((c) => c.kind === "expense"));
  renderUpcoming([...s.overdue, ...s.upcoming]);
}

function renderCategories(list) {
  const el = $("#categories");
  if (!list.length) {
    el.innerHTML = `<div class="empty"><strong>Nada gasto ainda</strong>As despesas pagas do mês aparecem aqui.</div>`;
    return;
  }
  const total = list.reduce((acc, c) => acc + c.total_cents, 0);
  el.innerHTML = `
    <div class="stack">${list.map((c) => `<span style="--c:${colorFor(c.category)};width:${(c.total_cents / total) * 100}%" title="${esc(c.category)}"></span>`).join("")}</div>
    <div class="legend">${list.map((c) => `
      <div class="legend-row" style="--c:${colorFor(c.category)}">
        <i></i><span>${esc(c.category)}</span>
        <span class="pct">${Math.round((c.total_cents / total) * 100)}%</span>
        <b>${money(c.total_cents)}</b>
      </div>`).join("")}
    </div>`;
}

function renderUpcoming(list) {
  const el = $("#upcoming");
  if (!list.length) {
    el.innerHTML = `<div class="empty"><strong>Tudo em dia</strong>Nenhuma conta vencida ou vencendo nos próximos 15 dias.</div>`;
    return;
  }
  const today = todayISO();
  el.innerHTML = list.map((t) => {
    const due = t.due_date || t.occurred_on;
    const d = parseISO(due);
    const late = due < today;
    const sub = late ? "Vencida" : due === today ? "Vence hoje" : `Vence em ${Math.round((d - parseISO(today)) / 86400000)} dia(s)`;
    return `<div class="due ${late ? "late" : ""}" data-id="${t.id}">
      <div class="due-date"><b>${String(d.getDate()).padStart(2, "0")}</b><span>${d.toLocaleDateString("pt-BR", { month: "short" }).replace(".", "")}</span></div>
      <div style="min-width:0"><div class="due-title">${esc(t.description)}</div><div class="due-sub">${sub}</div></div>
      <div class="due-amount">${money(t.amount_cents)}</div>
    </div>`;
  }).join("");
  el.querySelectorAll(".due").forEach((row) => {
    row.onclick = () => api(`/api/transactions/${row.dataset.id}`).then(openEditor);
  });
}

/* --- lista -------------------------------------------------------------- */

function dayLabel(iso) {
  const today = todayISO();
  const y = new Date(); y.setDate(y.getDate() - 1);
  const yesterday = `${y.getFullYear()}-${String(y.getMonth() + 1).padStart(2, "0")}-${String(y.getDate()).padStart(2, "0")}`;
  if (iso === today) return "Hoje";
  if (iso === yesterday) return "Ontem";
  return parseISO(iso).toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "long" }).replace(".", "");
}

async function loadTransactions() {
  const params = new URLSearchParams();
  if (filter === "review") params.set("needs_review", "true");
  else if (filter === "pending") params.set("status", "pending");
  else params.set("month", currentMonth());
  const q = $("#search").value.trim();
  if (q) params.set("q", q);
  transactions = await api(`/api/transactions?${params}`);
  $("#export").href = `/api/export.csv?month=${currentMonth()}`;
  renderTransactions();
}

function renderTransactions() {
  const el = $("#tx-list");
  if (!transactions.length) {
    const messages = {
      all: ["Nenhuma movimentação neste mês", "Envie um arquivo ou escreva uma mensagem acima para começar."],
      review: ["Nada para revisar", "Tudo o que foi lido automaticamente já foi conferido."],
      pending: ["Sem pendências", "Nenhuma conta aguardando pagamento."],
    };
    const [title, sub] = $("#search").value.trim() ? ["Nada encontrado", "Tente outro termo de busca."] : messages[filter];
    el.innerHTML = `<div class="empty"><strong>${title}</strong>${sub}</div>`;
    return;
  }
  const today = todayISO();
  const groups = new Map();
  for (const t of transactions) {
    if (!groups.has(t.occurred_on)) groups.set(t.occurred_on, []);
    groups.get(t.occurred_on).push(t);
  }
  let html = "";
  for (const [day, items] of groups) {
    const net = items.filter((t) => t.status === "paid").reduce((acc, t) => acc + (t.kind === "income" ? t.amount_cents : -t.amount_cents), 0);
    html += `<div class="tx-day"><span>${dayLabel(day)}</span><span>${net ? (net > 0 ? "+" : "−") + " " + money(Math.abs(net)) : ""}</span></div>`;
    html += items.map((t) => txRow(t, today)).join("");
  }
  el.innerHTML = html;
}

function txRow(t, today) {
  const color = colorFor(t.category);
  const name = t.counterparty || t.description;
  const initial = (name.match(/[A-Za-zÀ-ÿ0-9]/)?.[0] || "?").toUpperCase();
  const meta = [t.category, t.payment_method, t.account].filter(Boolean).map(esc).join(" · ");
  const pills = [];
  if (t.status === "pending") {
    const due = t.due_date || t.occurred_on;
    const late = due < today;
    pills.push(`<span class="pill ${late ? "late" : "pending"}">${icon("clock")}${late ? "vencida" : t.kind === "income" ? "a receber" : "vence"} ${fmtShort(due)}</span>`);
  }
  if (t.needs_review) pills.push(`<span class="pill review">${icon("alert")}revisar</span>`);
  const actions = [];
  if (t.needs_review) actions.push(`<button class="act" data-act="confirm" data-id="${t.id}">${icon("check")}Confirmar</button>`);
  if (t.status === "pending") actions.push(`<button class="act" data-act="pay" data-id="${t.id}">${t.kind === "income" ? "Recebido" : "Pago"}</button>`);
  const note = t.needs_review && t.notes ? `<div class="tx-note">${esc(t.notes.split("\n")[0])}</div>` : "";
  return `<div class="tx" data-id="${t.id}">
    <div class="avatar" style="--c:${color}">${esc(initial)}</div>
    <div style="min-width:0">
      <div class="tx-title">${esc(t.description)}</div>
      <div class="tx-meta">${meta}</div>
      ${note}
      ${pills.length || actions.length ? `<div class="tx-actions">${pills.join("")}${actions.join("")}</div>` : ""}
    </div>
    <div class="tx-amount ${t.kind === "income" ? "in" : ""}">${t.kind === "income" ? "+" : "−"} ${money(t.amount_cents)}</div>
  </div>`;
}

async function refresh() {
  try { await Promise.all([loadSummary(), loadTransactions()]); }
  catch (e) { toast({ type: "error", title: "Não foi possível carregar", lines: [e.message] }); }
}

/* --- notificações ------------------------------------------------------- */

function toast({ type = "success", title, lines = [], timeout = 7000 }) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const ic = type === "error" ? "x" : type === "info" ? "alert" : "check";
  el.innerHTML = `<span class="toast-icon">${icon(ic)}</span>
    <div style="min-width:0"><strong>${esc(title)}</strong>${lines.length ? `<ul>${lines.join("")}</ul>` : ""}</div>
    <button class="icon-btn" aria-label="Fechar">${icon("x")}</button>`;
  const close = () => { el.classList.add("out"); setTimeout(() => el.remove(), 200); };
  el.querySelector("button").onclick = close;
  $("#toasts").appendChild(el);
  if (timeout) setTimeout(close, timeout);
}

function reportResult(r) {
  const title = r.filename || "Mensagem";
  if (r.error) return toast({ type: "error", title, lines: [`<li>${esc(r.error)}</li>`], timeout: 12000 });
  const lines = [];
  for (const t of r.created || []) lines.push(`<li>Registrado: ${esc(t.description)} — ${money(t.amount_cents)}${t.needs_review ? " (revisar)" : ""}</li>`);
  for (const t of r.updated || []) lines.push(`<li>Baixa no pagamento: ${esc(t.description)} — ${money(t.amount_cents)}</li>`);
  for (const t of r.duplicates || []) lines.push(`<li class="muted">Já registrado: ${esc(t.description)}</li>`);
  for (const w of r.warnings || []) lines.push(`<li class="muted">${esc(w)}</li>`);
  const ok = (r.created?.length || 0) + (r.updated?.length || 0) > 0;
  toast({ type: ok ? "success" : "info", title, lines, timeout: ok ? 8000 : 12000 });
}

/* --- envio -------------------------------------------------------------- */

async function uploadFiles(fileList) {
  if (!fileList.length) return;
  const drop = $("#drop");
  const form = new FormData();
  [...fileList].forEach((f) => form.append("files", f));
  drop.classList.add("busy");
  $(".drop-title").textContent = `Lendo ${fileList.length === 1 ? "1 arquivo" : `${fileList.length} arquivos`}…`;
  try { (await api("/api/ingest/files", { method: "POST", body: form })).forEach(reportResult); }
  catch (e) { toast({ type: "error", title: "Falha no envio", lines: [`<li>${esc(e.message)}</li>`] }); }
  drop.classList.remove("busy");
  $(".drop-title").textContent = "Solte arquivos aqui ou toque para escolher";
  $("#files").value = "";
  refresh();
}

/* --- edição ------------------------------------------------------------- */

function setKind(kind, selectedCategory) {
  const form = $("#edit-form");
  form.kind.value = kind;
  document.querySelectorAll("#kind-switch button").forEach((b) => b.classList.toggle("active", b.dataset.kind === kind));
  const list = categories[kind] || [];
  const opts = !selectedCategory || list.includes(selectedCategory) ? list : [selectedCategory, ...list];
  $("#cat-select").innerHTML = opts.map((c) => `<option ${c === selectedCategory ? "selected" : ""}>${esc(c)}</option>`).join("");
}

function openEditor(tx) {
  editing = tx;
  const f = $("#edit-form");
  $("#edit-title").textContent = tx ? "Editar lançamento" : "Novo lançamento";
  $("#delete-btn").hidden = !tx;
  const t = tx || { kind: "expense", status: "paid", occurred_on: todayISO() };
  setKind(t.kind, t.category);
  f.status.value = t.status;
  f.amount.value = t.amount_cents != null ? (t.amount_cents / 100).toFixed(2).replace(".", ",") : "";
  f.occurred_on.value = t.occurred_on || "";
  f.description.value = t.description || "";
  f.due_date.value = t.due_date || "";
  f.counterparty.value = t.counterparty || "";
  f.payment_method.value = t.payment_method || "";
  f.account.value = t.account || "";
  f.notes.value = t.notes || "";
  const notes = $("#edit-notes");
  notes.hidden = !(tx && tx.needs_review && tx.notes);
  notes.textContent = tx?.notes || "";
  $("#editor").returnValue = "";
  $("#editor").showModal();
  if (!tx) f.amount.focus();
}

async function saveEditor() {
  const f = $("#edit-form");
  const data = {
    kind: f.kind.value, status: f.status.value, amount: f.amount.value, description: f.description.value,
    category: f.category.value, occurred_on: f.occurred_on.value, due_date: f.due_date.value || null,
    counterparty: f.counterparty.value || null, payment_method: f.payment_method.value || null,
    account: f.account.value || null, notes: f.notes.value || null,
  };
  try {
    if (editing) await api(`/api/transactions/${editing.id}`, jsonBody("PATCH", { ...data, needs_review: false }));
    else await api("/api/transactions", jsonBody("POST", data));
    toast({ title: editing ? "Lançamento atualizado" : "Lançamento registrado", timeout: 3500 });
  } catch (e) {
    toast({ type: "error", title: "Não foi possível salvar", lines: [`<li>${esc(e.message)}</li>`] });
  }
  refresh();
}

/* --- início ------------------------------------------------------------- */

function setFilter(value) {
  filter = value;
  document.querySelectorAll("[data-filter]").forEach((b) => b.classList.toggle("active", b.dataset.filter === value));
  loadTransactions();
}

async function init() {
  const now = new Date();
  $("#month").value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  renderMonthLabel();
  const [cats, health] = await Promise.all([api("/api/categories"), api("/api/health")]);
  categories = cats;
  $("#ai-status").textContent = health.ai_configured
    ? `Leitura inteligente ativa · ${health.model}`
    : "Modo básico · configure OPENROUTER_API_KEY para ler imagens e PDFs";

  $("#prev").onclick = () => shiftMonth(-1);
  $("#next").onclick = () => shiftMonth(1);
  $("#month").onchange = () => { renderMonthLabel(); refresh(); };
  document.querySelectorAll("[data-filter]").forEach((b) => { b.onclick = () => setFilter(b.dataset.filter); });
  $("#alerts").onclick = (e) => {
    const link = e.target.closest("[data-goto]");
    if (link) { e.preventDefault(); setFilter(link.dataset.goto); $("#tx-list").scrollIntoView({ behavior: "smooth", block: "start" }); }
  };
  let searchTimer;
  $("#search").oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadTransactions, 250); };

  const drop = $("#drop");
  $("#files").onchange = (e) => uploadFiles(e.target.files);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); uploadFiles(e.dataTransfer.files); };
  document.addEventListener("paste", (e) => {
    if (e.target.closest("input, textarea")) return;
    const files = [...(e.clipboardData?.files || [])];
    if (files.length) uploadFiles(files);
  });

  const text = $("#text");
  text.oninput = () => { text.style.height = "auto"; text.style.height = `${text.scrollHeight}px`; };
  text.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#text-form").requestSubmit(); } };
  $("#text-form").onsubmit = async (e) => {
    e.preventDefault();
    const value = text.value.trim();
    if (!value) return;
    const btn = $("#send-btn");
    btn.disabled = true;
    try { reportResult(await api("/api/ingest/text", jsonBody("POST", { text: value }))); text.value = ""; text.oninput(); }
    catch (err) { toast({ type: "error", title: "Mensagem não registrada", lines: [`<li>${esc(err.message)}</li>`], timeout: 12000 }); }
    btn.disabled = false;
    refresh();
  };
  $("#manual-btn").onclick = () => openEditor(null);

  $("#tx-list").onclick = async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (btn) {
      e.stopPropagation();
      try {
        await api(`/api/transactions/${btn.dataset.id}/${btn.dataset.act}`, jsonBody("POST", {}));
        toast({ title: btn.dataset.act === "pay" ? "Marcado como pago" : "Lançamento confirmado", timeout: 3000 });
      } catch (err) { toast({ type: "error", title: "Ação não concluída", lines: [`<li>${esc(err.message)}</li>`] }); }
      return refresh();
    }
    const row = e.target.closest(".tx[data-id]");
    if (row) openEditor(transactions.find((t) => t.id === Number(row.dataset.id)));
  };

  document.querySelectorAll("#kind-switch button").forEach((b) => { b.onclick = () => setKind(b.dataset.kind, null); });
  $("#editor").onclose = () => { if ($("#editor").returnValue === "save") saveEditor(); };
  $("#delete-btn").onclick = async () => {
    if (!editing || !confirm("Excluir este lançamento? Esta ação não pode ser desfeita.")) return;
    try {
      await api(`/api/transactions/${editing.id}`, { method: "DELETE" });
      toast({ title: "Lançamento excluído", timeout: 3000 });
    } catch (err) { toast({ type: "error", title: "Não foi possível excluir", lines: [`<li>${esc(err.message)}</li>`] }); }
    $("#editor").close("cancel");
    refresh();
  };

  refresh();
}

init();
