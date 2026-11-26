const $ = (sel) => document.querySelector(sel);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const vnd = (n) => Math.round(n).toLocaleString("vi-VN") + " ₫";
const shortTime = (iso) => new Date(iso).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
let sessionId = null;

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "object" ? detail.message : detail || res.statusText);
  }
  return data;
}

function addNode(html, className) {
  const node = document.createElement("div");
  node.className = className;
  node.innerHTML = html;
  $("#messages").appendChild(node);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return node;
}

function renderCard(card) {
  if (card.type === "balance") {
    return addNode(`<h4>Số dư tài khoản ${esc(card.account_masked)}</h4><div class="row"><span>Khả dụng</span><strong>${vnd(card.available_balance)}</strong></div>`, "card");
  }
  if (card.type === "spending") {
    const rows = card.breakdown.map((b) => `
      <div class="row"><div style="flex:1">${esc(b.label)}<div class="bar"><div style="width:${b.percent}%"></div></div></div>
      <div>${vnd(b.amount)}<div class="sub">${b.percent}%</div></div></div>`).join("");
    return addNode(`<h4>${esc(card.title)} · ${vnd(card.total)}</h4>${rows}`, "card");
  }
  if (card.type === "transactions") {
    const rows = card.items.map((t) => `
      <div class="row"><div>${esc(t.description)}<div class="sub">${shortTime(t.posted_at)} · ${esc(t.category_label)}</div></div>
      <div class="${t.amount < 0 ? "neg" : "pos"}">${t.amount < 0 ? "−" : "+"}${vnd(Math.abs(t.amount))}</div></div>`).join("");
    return addNode(`<h4>${esc(card.title)}</h4>${rows || "Không có giao dịch"}`, "card");
  }
  if (card.type === "beneficiaries") {
    const rows = card.items.map((b) => `<div class="row"><div>${esc(b.name)}<div class="sub">${esc(b.bank)} ${esc(b.account_masked)}</div></div><div class="sub">gọi là: ${esc(b.aliases.join(", "))}</div></div>`).join("");
    return addNode(`<h4>Danh bạ người nhận</h4>${rows}`, "card");
  }
  if (card.type === "transfer_confirm") return renderConfirm(card.transfer);
  return null;
}

function renderConfirm(t) {
  const node = addNode(`
    <h4>Xác nhận chuyển tiền</h4>
    <div class="amount">${vnd(t.amount)}</div>
    <div class="row"><span>Người nhận</span><strong>${esc(t.beneficiary.name)}</strong></div>
    <div class="row"><span>Ngân hàng</span><span>${esc(t.beneficiary.bank)} ${esc(t.beneficiary.account_masked)}</span></div>
    <div class="row"><span>Hết hạn OTP</span><span>${shortTime(t.expires_at)}</span></div>
    <div class="warnline">Kiểm tra kỹ người nhận và số tiền. Lệnh chỉ được thực hiện khi bạn nhập đúng OTP.</div>
    <form><input inputmode="numeric" maxlength="6" placeholder="Mã OTP" required><button>Xác nhận</button>
    <button type="button" class="secondary">Hủy</button></form>
    <div class="result"></div>`, "card confirm");
  const form = node.querySelector("form");
  const result = node.querySelector(".result");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const otp = form.querySelector("input").value.trim();
    if (!/^\d{6}$/.test(otp)) { result.innerHTML = '<span class="neg">Nhập đủ 6 chữ số OTP.</span>'; return; }
    try {
      const r = await api(`/api/transfers/${t.transfer_id}/confirm`, { otp });
      result.innerHTML = `<span class="pos">✔ Chuyển thành công ${vnd(r.amount)}. Số dư mới: ${vnd(r.new_balance ?? 0)}</span>`;
      form.remove();
      hideSms();
      refreshHeader();
    } catch (err) {
      result.innerHTML = `<span class="neg">${esc(err.message)}</span>`;
    }
    loadAudit();
  });
  form.querySelector(".secondary").addEventListener("click", async () => {
    await api(`/api/transfers/${t.transfer_id}/cancel`, {}).catch(() => null);
    result.textContent = "Đã hủy lệnh chuyển.";
    form.remove();
    hideSms();
    loadAudit();
  });
  if (t.demo_otp) showSms(t.demo_otp, t.amount);
  return node;
}

function showSms(otp, amount) {
  const box = $("#sms");
  box.innerHTML = `<small>SMS GIẢ LẬP · Ngân hàng Demo</small>Mã OTP xác nhận chuyển ${vnd(amount)} là <strong>${esc(otp)}</strong>. Tuyệt đối không cung cấp mã này cho bất kỳ ai, kể cả trợ lý chat.`;
  box.classList.remove("hidden");
  clearTimeout(showSms.timer);
  showSms.timer = setTimeout(hideSms, 60000);
}
function hideSms() { $("#sms").classList.add("hidden"); }

function renderTrace(trace, intent, blocked) {
  const steps = trace.map((s) => {
    if (s.step === "guardrail") {
      return `<li>Guardrail ${s.allowed ? '<span class="tag">cho qua</span>' : `<span class="tag bad">chặn: ${esc(s.category)}</span>`}</li>`;
    }
    if (s.step === "understand") {
      return `<li>Hiểu ý định bằng <code>${s.source === "rules" ? "luật (offline)" : esc(s.source)}</code>: <code>${esc(s.name)}</code> ${esc(JSON.stringify(s.slots))}</li>`;
    }
    if (s.step === "tool") {
      return `<li>Gọi API lõi <code>${esc(s.name)}</code> ${s.ok ? '<span class="tag">OK</span>' : `<span class="tag bad">${esc(s.error)}</span>`} <span class="hint">${s.ms} ms</span></li>`;
    }
    return "";
  }).join("");
  const end = blocked
    ? "<li>Trả lời bằng thông báo cố định; tin nhắn không được gửi tới mô hình hay API lõi</li>"
    : "<li>Trả lời bằng mẫu câu cố định; mọi con số lấy từ kết quả API lõi</li>";
  $("#trace").innerHTML = steps + end;
}

function renderSuggestions(list) {
  $("#suggestions").innerHTML = (list || []).map((s) => `<button class="chip" type="button">${esc(s)}</button>`).join("");
  $("#suggestions").querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => send(c.textContent)));
}

async function send(text) {
  const message = text.trim();
  if (!message) return;
  addNode(esc(message), "msg user");
  renderSuggestions([]);
  try {
    const r = await api("/api/chat", { message, session_id: sessionId });
    sessionId = r.session_id;
    addNode(esc(r.reply), r.blocked ? "msg bot blocked" : "msg bot");
    r.cards.forEach(renderCard);
    renderSuggestions(r.suggestions);
    renderTrace(r.trace, r.intent, r.blocked);
  } catch (err) {
    addNode(esc("Lỗi: " + err.message), "msg bot blocked");
  }
  loadAudit();
}

async function loadAudit() {
  try {
    const items = await api("/api/audit?limit=25");
    $("#audit").innerHTML = items.map((e) => {
      let what = esc(e.event);
      if (e.event === "chat") what = `chat · <code>${esc(e.intent ? e.intent.name : "?")}</code> · ${esc(e.message)}`;
      if (e.event === "security_event") what = `<span class="neg">chặn ${esc(e.blocked)}</span> · ${esc(e.message)}`;
      if (e.event === "transfer_confirmed") what = `<span class="pos">chuyển thành công</span> ${vnd(e.amount)} → ${esc(e.beneficiary)}`;
      if (e.event === "transfer_confirm_failed") what = `<span class="neg">xác nhận thất bại</span> · ${esc(e.code)}`;
      return `<li><span class="t">${esc(e.at)}</span><br>${what}</li>`;
    }).join("") || "<li>Chưa có bản ghi</li>";
  } catch {
    $("#audit").innerHTML = "<li>Không tải được nhật ký</li>";
  }
}

async function refreshHeader() {
  const me = await api("/api/me").catch(() => null);
  if (!me) return;
  $("#customer").textContent = me.customer;
  $("#account").textContent = "Tài khoản " + me.account_masked;
  $("#balance").textContent = vnd(me.available_balance);
}

async function init() {
  const health = await api("/health").catch(() => ({}));
  $("#llm").textContent = "LLM: " + (health.llm_provider || "?");
  $("#core").textContent = "Core: " + (health.core || "?");
  refreshHeader();
  addNode("Xin chào! Mình có thể xem số dư, thống kê chi tiêu, liệt kê giao dịch và soạn lệnh chuyển tiền (cần OTP). Bạn cần gì?", "msg bot");
  renderSuggestions(["Số dư của tôi", "Tháng này tôi tiêu bao nhiêu?", "Chi ăn uống tháng trước", "Chuyển 500k cho mẹ"]);
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send($("#input").value); $("#input").value = ""; });
  document.querySelectorAll(".chips .chip").forEach((c) => c.addEventListener("click", () => send(c.dataset.q)));
  $("#refresh").addEventListener("click", loadAudit);
  loadAudit();
}

init();
