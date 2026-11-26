const $ = (sel) => document.querySelector(sel);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const vnd = (n) => (n === null || n === undefined ? "—" : Math.round(n).toLocaleString("vi-VN") + " ₫");
const STATUS = { PASS: "Đạt", FAIL: "Không đạt", NEED_INFO: "Cần bổ sung" };
const FIELD_LABELS = {
  full_name: "Họ tên", id_number: "Số CCCD", date_of_birth: "Ngày sinh", expiry_date: "Hiệu lực đến",
  requested_amount: "Số tiền vay", term_months: "Thời hạn (tháng)", purpose: "Mục đích",
  existing_monthly_debt: "Nợ hiện tại/tháng", employer: "Đơn vị", contract_type: "Loại HĐLĐ",
  start_date: "Ngày bắt đầu", end_date: "Ngày kết thúc", monthly_salary: "Lương HĐLĐ",
  account_holder: "Chủ tài khoản", account_number: "Số tài khoản",
};
let samplesIndex = [];

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function maskId(value) {
  const s = String(value ?? "");
  return s.length > 3 ? "*".repeat(s.length - 3) + s.slice(-3) : s;
}

function showValue(name, value) {
  if (value === null || value === undefined) return "—";
  if (name === "id_number" || name === "account_number") return maskId(String(value).replace(/\s/g, ""));
  if (["requested_amount", "existing_monthly_debt", "monthly_salary"].includes(name)) return vnd(value);
  if (value === "khong thoi han") return "Không thời hạn";
  return value;
}

function evidenceHtml(list) {
  if (!list || !list.length) return "";
  return list.map((e) => `<div class="evidence">📄 ${esc(e.filename)} · trang ${esc(e.page)}${e.method === "llm" ? " · trích bởi LLM" : ""}: <code>${esc(e.raw)}</code></div>`).join("");
}

function renderResult(r) {
  const f = r.facts;
  const n = r.narrative;
  const sample = samplesIndex.find((s) => s.case_id === r.case_id);
  const docLinks = sample
    ? r.extraction.documents.map((d) => `<a href="/samples/${esc(sample.folder)}/${esc(d.filename)}" target="_blank">${esc(d.label)}</a>`).join("")
    : "";
  const rules = r.rules.map((rule) => `
    <tr>
      <td><span class="status ${rule.status}">${STATUS[rule.status]}</span></td>
      <td><strong>${esc(rule.title)}</strong><div>${esc(rule.detail)}</div>
        <details><summary>${rule.clause_id.startsWith("Điều") ? esc(rule.clause_id) : "Điều " + esc(rule.clause_id)} · xem điều khoản và bằng chứng</summary>
          <div class="clause">${esc(rule.clause_text || "")}</div>${evidenceHtml(rule.evidence)}
        </details>
      </td>
    </tr>`).join("");
  const fields = Object.entries(r.extraction.fields).map(([docType, values]) => {
    const doc = r.extraction.documents.find((d) => d.doc_type === docType);
    const rows = Object.entries(values).map(([name, ev]) => `
      <tr><td>${esc(FIELD_LABELS[name] || name)}</td><td>${esc(showValue(name, ev.value))}</td>
      <td class="evidence">${esc(ev.filename)} · tr.${esc(ev.page)}${ev.method === "llm" ? " · LLM" : ""}</td></tr>`).join("");
    return `<h3>${esc(doc ? doc.label : docType)}</h3><table>${rows}</table>`;
  }).join("");
  const salaries = r.extraction.salary_credits.map((s) => `<li>${esc(s.date)}: ${vnd(s.amount)} — <code>${esc(s.description)}</code></li>`).join("");
  const list = (items) => items.map((x) => `<li>${esc(x)}</li>`).join("");

  $("#result").innerHTML = `
    <div class="verdict ${r.verdict}">
      <div class="label">${esc(r.verdict_label)}</div>
      <div class="meta">${esc(r.case_id)} · ${esc(r.applicant || "—")} · CCCD ${esc(r.applicant_id_masked)} · ngày thẩm định ${esc(r.as_of)} · audit ${esc(r.audit_id)}</div>
    </div>
    <div class="docs">${docLinks}</div>
    <div class="tiles">
      <div class="tile"><div class="k">Thu nhập xét duyệt</div><div class="v">${vnd(f.income_for_assessment)}</div></div>
      <div class="tile"><div class="k">Trả góp ước tính</div><div class="v">${vnd(f.estimated_installment)}</div></div>
      <div class="tile"><div class="k">Nợ hiện tại</div><div class="v">${vnd(f.existing_monthly_debt)}</div></div>
      <div class="tile"><div class="k">DTI (≤ 50%)</div><div class="v">${f.dti_percent ?? "—"}%</div></div>
    </div>
    <h2>Tờ trình tóm tắt</h2>
    <p class="summary">${esc(n.summary)}</p>
    <p class="source-note">Soạn bởi: ${n.source === "template" ? "mẫu cố định (chế độ offline)" : esc(n.source)}${n.fallback_reason ? " · LLM bị bỏ qua: " + esc(n.fallback_reason) : ""}</p>
    ${n.risks.length ? `<h3>Rủi ro / điều kiện không đạt</h3><ul class="risks">${list(n.risks)}</ul>` : ""}
    ${n.follow_ups.length ? `<h3>Việc cần làm với khách hàng</h3><ul class="followups">${list(n.follow_ups)}</ul>` : ""}
    <h2 class="spaced">Kiểm tra điều kiện (${r.rules.filter((x) => x.status === "PASS").length}/${r.rules.length} đạt)</h2>
    <table><tr><th>Kết quả</th><th>Điều kiện · chi tiết · căn cứ</th></tr>${rules}</table>
    <h2 class="spaced">Thông tin trích xuất từ hồ sơ</h2>
    ${fields}
    <h3>Các kỳ lương trên sao kê</h3><ul>${salaries || "<li>Không tìm thấy</li>"}</ul>
    ${r.extraction.warnings.length ? `<h3>Cảnh báo</h3><ul>${list(r.extraction.warnings)}</ul>` : ""}
    <div class="disclaimer">${esc(r.disclaimer)} Chính sách áp dụng: ${esc(r.policy_version)}.</div>`;
  loadAudit();
}

async function assessSample(caseId, button) {
  document.querySelectorAll(".sample").forEach((b) => b.classList.remove("active"));
  button.classList.add("active");
  $("#result").innerHTML = '<div class="empty">Đang thẩm định…</div>';
  try {
    renderResult(await api(`/api/assess/sample/${encodeURIComponent(caseId)}`, { method: "POST" }));
  } catch (err) {
    $("#result").innerHTML = `<div class="empty error">${esc(err.message)}</div>`;
  }
}

async function uploadFiles() {
  const input = $("#files");
  if (!input.files.length) {
    $("#result").innerHTML = '<div class="empty error">Chọn ít nhất một tệp trước khi thẩm định.</div>';
    return;
  }
  const form = new FormData();
  [...input.files].forEach((file) => form.append("files", file));
  $("#result").innerHTML = '<div class="empty">Đang đọc hồ sơ…</div>';
  try {
    renderResult(await api("/api/assess", { method: "POST", body: form }));
  } catch (err) {
    $("#result").innerHTML = `<div class="empty error">${esc(err.message)}</div>`;
  }
}

async function ask(question) {
  if (!question.trim()) return;
  const box = document.createElement("div");
  box.className = "answer";
  box.innerHTML = `<div class="q">${esc(question)}</div><div>Đang tìm…</div>`;
  $("#answers").prepend(box);
  try {
    const a = await api("/api/policy/ask", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }),
    });
    const cited = a.cited.length ? "Căn cứ: " + a.cited.map((c) => (c.startsWith("Điều") ? c : "Điều " + c)).join(", ") : "Không trích dẫn";
    box.innerHTML = `<div class="q">${esc(question)}</div><div>${esc(a.answer)}</div><div class="src">${esc(cited)} · ${esc(a.source)}</div>`;
  } catch (err) {
    box.innerHTML = `<div class="q">${esc(question)}</div><div class="error">${esc(err.message)}</div>`;
  }
  loadAudit();
}

async function loadAudit() {
  try {
    const items = await api("/api/audit?limit=12");
    $("#audit").innerHTML = items.map((e) => {
      const what = e.event === "credit_assessment"
        ? `Thẩm định ${esc(e.case_id)} → <strong>${esc(e.verdict)}</strong> (CCCD ${esc(e.applicant_id)})`
        : `Hỏi chính sách → ${esc((e.cited || []).join(", ") || "từ chối")}`;
      return `<li><span class="t">${esc(e.at)} · ${esc(e.audit_id)}</span><br>${what}</li>`;
    }).join("") || "<li>Chưa có bản ghi</li>";
  } catch {
    $("#audit").innerHTML = "<li>Không tải được nhật ký</li>";
  }
}

async function init() {
  const health = await api("/health").catch(() => ({}));
  $("#provider").textContent = "LLM: " + (health.provider || "?");
  $("#policy-version").textContent = "Chính sách " + (health.policy_version || "?");
  samplesIndex = await api("/api/samples").catch(() => []);
  $("#samples").innerHTML = samplesIndex.map((s) => `
    <button class="sample" data-case="${esc(s.case_id)}"><strong>${esc(s.case_id)} · ${esc(s.applicant)}</strong><span>${esc(s.title)}</span></button>`).join("");
  document.querySelectorAll(".sample").forEach((b) => b.addEventListener("click", () => assessSample(b.dataset.case, b)));
  $("#upload").addEventListener("click", uploadFiles);
  $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); ask($("#question").value); $("#question").value = ""; });
  document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => ask(c.dataset.q)));
  $("#refresh-audit").addEventListener("click", loadAudit);
  loadAudit();
}

init();
