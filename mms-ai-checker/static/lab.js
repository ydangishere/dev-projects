"use strict";
const $ = id => document.getElementById(id);
let token = "";
const fields = ["max_words","overlap","candidate_k","rrf_k","coverage_weight"];
function el(tag, text, cls) { const node=document.createElement(tag); if(text!==undefined)node.textContent=text; if(cls)node.className=cls; return node; }
function status(text) { $("status").textContent=text; }
async function api(path, options={}) {
  const headers={Authorization:`Bearer ${token}`,...options.headers};
  if(options.body)headers["Content-Type"]="application/json";
  const response=await fetch(path,{...options,headers,cache:"no-store"});
  if(!response.ok){ let message=`Lỗi ${response.status}`; try{const body=await response.json(); message=typeof body.detail==="string"?body.detail:message;}catch{} throw new Error(message); }
  return response.json();
}
function config() {
  const body={embedder:$("embedder").value,split:$("split").value,note:$("note").value.trim()};
  for(const f of fields)body[f]=Number($(f).value);
  return body;
}
function metricTable(record) {
  const table=el("table",undefined,"metrics");const head=el("tr");
  head.append(el("th","Chỉ số"),el("th","Lexical (cũ)"),el("th","Hybrid"));table.append(head);
  for(const name of Object.keys(record.hybrid)){
    const row=el("tr");const a=record.lexical_baseline[name],b=record.hybrid[name];
    row.append(el("td",name),el("td",a.toFixed(4)),el("td",b.toFixed(4),b>a?"better":b<a?"worse":""));table.append(row);
  }
  return table;
}
function showResult(record) {
  const box=$("result");box.replaceChildren();
  box.append(el("p",`${record.embedder} · bộ ${record.split} · ${record.questions} câu · ${record.processing_seconds}s · dữ liệu v${record.dataset_version}`,"muted"),metricTable(record));
  const list=el("details");list.append(el("summary","Từng câu hỏi (top 3 rule)"));
  for(const [qid,row] of Object.entries(record.per_question)){
    const expected=Object.keys(row.relevant).join(", ");
    list.append(el("div",`${qid} · đúng: ${expected} · lexical: ${row.lexical.join(" ")} · hybrid: ${row.hybrid.join(" ")}`,row.hybrid[0] in row.relevant?"doc":"doc miss"));
  }
  box.append(list);
}
async function loadHistory() {
  const items=await api("/api/lab/experiments");
  if(!items.length)return $("history").replaceChildren(el("p","Chưa có.","muted"));
  const table=el("table",undefined,"metrics");const head=el("tr");
  ["Thời gian","Ghi chú","Embedding","Bộ","Chunk/overlap","MRR cũ → hybrid","NDCG@5 cũ → hybrid"].forEach(t=>head.append(el("th",t)));table.append(head);
  for(const item of items){
    const row=el("tr");const s=item.settings;
    row.append(el("td",item.created_at.slice(0,19).replace("T"," ")),el("td",item.note||"—"),el("td",item.embedder),el("td",item.split),el("td",`${s.max_words}/${s.overlap}`),
      el("td",`${item.lexical_baseline.mrr.toFixed(3)} → ${item.hybrid.mrr.toFixed(3)}`),el("td",`${item.lexical_baseline["ndcg@5"].toFixed(3)} → ${item.hybrid["ndcg@5"].toFixed(3)}`));
    table.append(row);
  }
  $("history").replaceChildren(table);
}
$("connect").onclick=async()=>{
  token=$("token").value.trim();$("token").value="";
  try{await loadHistory();$("preview").disabled=false;$("run").disabled=false;status("Đã kết nối.");}
  catch(error){token="";status(error.message);}
};
$("preview").onclick=async()=>{
  try{
    const data=await api(`/api/lab/chunks?max_words=${Number($("max_words").value)}&overlap=${Number($("overlap").value)}`);
    $("chunks").replaceChildren(el("p",`${data.policy_id} v${data.policy_version} · ${data.chunks.length} chunk`,"muted"),...data.chunks.map(c=>{
      const node=el("div",undefined,"doc chunk");node.append(el("strong",`${c.id} · ${c.words} từ`),el("small",c.text));return node;
    }));
  }catch(error){status(error.message);}
};
$("run").onclick=async()=>{
  $("run").disabled=true;status("Đang chạy thử nghiệm…");
  try{const record=await api("/api/lab/experiments",{method:"POST",body:JSON.stringify(config())});showResult(record);await loadHistory();status("Đã lưu thử nghiệm.");}
  catch(error){status(error.message);}
  finally{$("run").disabled=false;}
};
