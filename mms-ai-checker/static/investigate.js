"use strict";
const $ = id => document.getElementById(id);
const MONEY = {
  not_captured: "Chưa thu tiền",
  refunded: "Đã hoàn tiền",
  unresolved: "Chưa xác định",
  captured_not_settled: "Đã thu, chưa quyết toán",
  settled_not_paid: "Đã quyết toán, chưa chi trả",
  paid: "Đã chi trả",
};
function el(tag, text, cls) { const node=document.createElement(tag); if(text!==undefined)node.textContent=text; if(cls)node.className=cls; return node; }
function status(text) { $("status").textContent=text; }
function item(entry, note) {
  const box=el("div",undefined,entry.kind==="cause"?"finding":"finding review");
  const head=el("div",undefined,"finding-head");
  head.append(el("b",entry.title),el("span",entry.kind==="cause"?"Đã có căn cứ":"Chưa xác định","pill"));
  box.append(head,el("p",note?note.text:entry.explanation));
  const details=Object.entries(entry.params).filter(([,v])=>v!==null).map(([k,v])=>`${k}: ${v}`).join(" · ");
  if(details)box.append(el("p",details,"muted"));
  box.append(el("p",`Nguồn: ${entry.sources.join(", ")}`,"muted"));
  const steps=el("ol");for(const step of entry.steps)steps.append(el("li",step));box.append(steps);
  if(entry.screen)box.append(el("p",`Màn hình MMS: ${entry.screen}`,"check-meta"));
  if(entry.escalate_to)box.append(el("p",`Chuyển: ${entry.escalate_to}`,"warning"));
  if(!entry.can_act)box.append(el("p",`Bước này cần vai trò ${entry.requires_role} hoặc checker.`,"muted"));
  return box;
}
function render(r) {
  const box=$("result");box.replaceChildren();box.hidden=false;
  box.append(el("p",`${r.transaction_id} · ${r.merchant_id} · nguồn ${r.bank_source} · quy trình ${r.procedure_id} v${r.procedure_version} · giải thích ${r.explanation_mode}`,"check-meta"));
  box.append(el("h2",MONEY[r.money_status]||r.money_status),el("p",r.summary));
  const notes=Object.fromEntries(r.notes.map(n=>[n.code,n]));
  for(const entry of [...r.causes,...r.open_questions])box.append(item(entry,notes[entry.code]));
  const facts=el("details");facts.append(el("summary",`Dữ kiện từ hệ thống (${r.facts.length})`));
  for(const f of r.facts)facts.append(el("div",`[${f.source}] ${f.text}`,"doc"));
  const timeline=el("details");timeline.append(el("summary",`Nhật ký (${r.timeline.length})`));
  for(const e of r.timeline)timeline.append(el("div",`${e.at} · ${e.service} · ${e.event}`,"doc"));
  box.append(facts,timeline,el("p",`Hành động: nhân viên quyết định · không tự chuyển tiền`,"muted"));
}
async function run() {
  const token=$("token").value.trim(), txn=$("txn").value.trim();
  if(!token||!txn)return status("Cần mã truy cập và mã giao dịch.");
  status("Đang tra cứu…");$("go").disabled=true;
  try{
    const response=await fetch("/api/investigations",{method:"POST",cache:"no-store",headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},body:JSON.stringify({transaction_id:txn,question:$("question").value.trim()||undefined})});
    const body=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(typeof body.detail==="string"?body.detail:`Lỗi ${response.status}`);
    render(body);status("Xong.");
  }catch(error){status(error.message);$("result").hidden=true;}
  finally{$("go").disabled=false;}
}
$("go").addEventListener("click",run);
$("txn").addEventListener("keydown",e=>{if(e.key==="Enter")run();});
