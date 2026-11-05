"use strict";
const $ = id => document.getElementById(id);
let token = "", applicationId = "", currentCheck = null, epoch = 0, sourceUrl = null;
const names = {business_license:"Đăng ký kinh doanh",representative_id:"Giấy tờ người đại diện",bank_confirmation:"Xác nhận tài khoản"};
function el(tag, text, cls) { const node=document.createElement(tag); if(text!==undefined)node.textContent=text; if(cls)node.className=cls; return node; }
function status(text) { $("status").textContent=text; }
async function api(path, options={}) {
  const headers={Authorization:`Bearer ${token}`,...options.headers};
  if(options.body && !(options.body instanceof FormData))headers["Content-Type"]="application/json";
  const response=await fetch(path,{...options,headers,cache:"no-store"});
  if(!response.ok){ let message=`Lỗi ${response.status}`; try{const body=await response.json(); message=typeof body.detail==="string"?body.detail:message;}catch{} throw new Error(message); }
  return response;
}
function invalidate() {
  epoch++;currentCheck=null;
  $("answer").replaceChildren(el("p","Chạy kiểm tra để xem kết quả của hồ sơ hiện tại.","muted"));
  $("evidence").replaceChildren(el("p","Chưa chọn bằng chứng.","muted"));
  if(sourceUrl){URL.revokeObjectURL(sourceUrl);sourceUrl=null;}
}
async function loadApplication() {
  invalidate();applicationId=$("application").value;
  const requestEpoch=epoch;$("check").disabled=true;
  const record=await (await api(`/api/applications/${encodeURIComponent(applicationId)}`)).json();
  if(requestEpoch!==epoch)return;
  $("merchant").textContent=record.legal_name;$("description").textContent=record.description;
  $("documents").replaceChildren(...record.documents.map(d=>{
    const node=el("div",undefined,"doc");node.append(el("strong",names[d.kind]),el("small",`v${d.version} · ${d.verification==="verified"&&d.verified_version===d.version?"Đã xác minh phiên bản":"Chờ xác minh"}`));return node;
  }));
  $("check").disabled=false;status(`Đã mở ${record.id} · phiên bản hồ sơ ${record.revision}.`);
}
$("connect").onclick=async()=>{
  token=$("token").value.trim();$("token").value="";invalidate();
  try{
    const records=await (await api("/api/applications")).json();
    $("application").replaceChildren(...records.map(r=>{const option=el("option",`${r.id} · ${r.legal_name}`);option.value=r.id;return option;}));
    $("application").disabled=false;
    if(records.length)await loadApplication();else status("Không có hồ sơ được phép xem.");
  }catch(error){token="";$("application").disabled=true;$("check").disabled=true;status(error.message);}
};
$("disconnect").onclick=()=>{
  token="";applicationId="";invalidate();$("application").replaceChildren(el("option","Chưa kết nối"));
  $("application").disabled=true;$("check").disabled=true;$("documents").replaceChildren();$("merchant").textContent="Chọn hồ sơ";$("description").textContent="";status("Đã đăng xuất.");
};
$("application").onchange=()=>loadApplication().catch(e=>status(e.message));
$("upload").onclick=async()=>{
  if(!applicationId || !token)return status("Kết nối và chọn hồ sơ trước.");
  const file=$("file").files[0];if(!file)return status("Chọn giấy tờ cần tải lên.");
  const body=new FormData();body.append("kind",$("kind").value);body.append("file",file);
  const id=applicationId;invalidate();$("upload").disabled=true;
  try{await api(`/api/applications/${encodeURIComponent(id)}/documents`,{method:"POST",body});$("file").value="";if(id===applicationId)await loadApplication();status("Đã cập nhật giấy tờ; cần kiểm tra lại và xác minh phiên bản mới.");}
  catch(error){status(error.message);}
  finally{$("upload").disabled=false;}
};
$("check").onclick=async()=>{
  invalidate();const requestEpoch=epoch;$("check").disabled=true;status("Đang đọc hồ sơ → tìm quy định → kiểm tra → giải thích…");
  try{
    const result=await(await api(`/api/applications/${encodeURIComponent(applicationId)}/checks`,{method:"POST",body:JSON.stringify({question:$("question").value})})).json();
    if(requestEpoch!==epoch)return;currentCheck=result;render(result);status("Đã kiểm tra. Chọn căn cứ để đối chiếu trước khi quyết định.");
  }catch(error){if(requestEpoch===epoch)status(error.message);}
  finally{if(requestEpoch===epoch)$("check").disabled=false;}
};
function render(result){
  const container=$("answer");container.replaceChildren(el("h2",result.summary));
  if(result.stale)container.append(el("p","Hồ sơ đã thay đổi. Kết quả này chỉ là lịch sử; cần kiểm tra lại.","warning"));
  container.append(el("p",`${result.mode} · giải thích ${result.explanation_mode} · ${result.policy_id} v${result.policy_version} · ${result.review_date}`,"check-meta"));
  if(result.events.length)container.append(el("p","Có bước AI không hoàn thành hoặc đầu vào đáng ngờ. Xem cảnh báo và kiểm tra thủ công.","warning"));
  const notes=new Map(result.notes.map(n=>[n.finding_id,n.text]));
  for(const finding of result.findings){
    const card=el("article",undefined,"finding"),head=el("div",undefined,"finding-head");
    head.append(el("span",finding.severity==="blocker"?"CẦN BỔ SUNG / HẾT HẠN":"CẦN ĐỐI CHIẾU",finding.severity),el("span",`${finding.id} · ${finding.rule}`));
    card.append(head,el("p",finding.message));
    if(notes.get(finding.id)!==finding.message)card.append(el("p",notes.get(finding.id),"muted"));
    const actions=el("div",undefined,"row"),view=el("button","Xem căn cứ","secondary");
    view.onclick=()=>showEvidence(result.id,finding.id).catch(e=>status(e.message));actions.append(view);
    const feedback=el("select",undefined,"feedback");feedback.setAttribute("aria-label",`Đánh giá ${finding.id}`);
    for(const [value,label] of [["correct","Đúng"],["incorrect","Sai"],["needs_review","Chưa rõ"]]){const option=el("option",label);option.value=value;feedback.append(option);}
    const save=el("button","Gửi đánh giá","secondary");save.disabled=result.stale;
    save.onclick=async()=>{try{await api(`/api/checks/${result.id}/feedback`,{method:"POST",body:JSON.stringify({finding_id:finding.id,verdict:feedback.value,note:""})});status("Đã lưu đánh giá. Không thay đổi quyết định duyệt.");}catch(e){status(e.message);}};
    actions.append(feedback,save);card.append(actions);container.append(card);
  }
  container.append(el("p",`Mã lần kiểm tra: ${result.id} · Nguồn và quy định được lưu theo thời điểm kiểm tra.`,"check-meta"));
}
async function showEvidence(checkId,findingId){
  const requestEpoch=epoch;
  const evidence=await(await api(`/api/checks/${checkId}/evidence/${findingId}`)).json();if(requestEpoch!==epoch)return;
  const box=$("evidence");box.replaceChildren(el("h3",`${findingId} · ${evidence.finding.rule}`));
  if(evidence.stale)box.append(el("p","Bằng chứng lịch sử; hồ sơ hiện tại đã thay đổi.","warning"));
  if(evidence.document)box.append(el("p",`${names[evidence.document.kind]} · v${evidence.document.version} · ${evidence.finding.page?`trang ${evidence.finding.page}`:"danh sách hồ sơ"}`,"muted"));
  else box.append(el("p","Nguồn: danh sách giấy tờ tại thời điểm kiểm tra. Giấy tờ này chưa có trong hồ sơ.","muted"));
  if(evidence.finding.quote)box.append(el("pre",evidence.finding.quote));
  box.append(el("pre",evidence.policy.text));
  if(evidence.original_url){
    const source=await(await api(evidence.original_url)).blob();if(requestEpoch!==epoch)return;
    if(sourceUrl)URL.revokeObjectURL(sourceUrl);sourceUrl=URL.createObjectURL(source);
    if(evidence.document.mime==="text/plain")box.append(el("pre",await source.text()));
    else if(evidence.document.mime.startsWith("image/")){const image=el("img");image.src=sourceUrl;image.alt="Giấy tờ gốc cần đối chiếu";box.append(image);}
    else{const frame=el("iframe");frame.src=sourceUrl;frame.title="PDF gốc";box.append(frame);}
    const download=el("a","Tải bản gốc để đối chiếu");download.href=sourceUrl;download.download="source";box.append(download);
  }
  box.scrollIntoView({behavior:"smooth",block:"start"});
}
fetch("/healthz").then(r=>r.json()).then(h=>{$("mode").textContent=h.mode==="demo"?"DEMO · không gọi AI":`Gemini · ${h.model}`;}).catch(()=>{$("mode").textContent="Chưa kết nối máy chủ";});
