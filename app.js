const P=window.PLAN||{subjects:{}},C=P.calendar||{weeks:[],phases:[]},S=P.subjects;
const $=s=>document.querySelector(s),app=$("#app");const DN=["周日","周一","周二","周三","周四","周五","周六"];
let storageOK=true;let done={};
try{const v=JSON.parse(localStorage.getItem("planDone")||"{}");if(v&&typeof v==="object"&&!Array.isArray(v))done=v;}catch(e){storageOK=false;}
const save=()=>{try{localStorage.setItem("planDone",JSON.stringify(done));}catch(e){storageOK=false;}};
// 固定北京时间，日期与星期都在同一个偏移坐标内计算；凌晨04:00换学习日。
function studyDate(now=Date.now()){return new Date(now+(8-4)*3600e3);}
const iso=t=>t.toISOString().slice(0,10);
function weekOf(dt){const s=iso(dt);return C.weeks.find(w=>w.monday<=s&&s<=w.sunday);}
function countdown(now=Date.now()){const today=new Date(now+8*3600e3).toISOString().slice(0,10);return Math.max(0,Math.round((Date.parse(C.gaokao+"T00:00:00Z")-Date.parse(today+"T00:00:00Z"))/864e5));}
const phaseName=id=>(C.phases.find(p=>p.id===id)||{}).name||id;
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));}
function safeUrl(u){const s=String(u||"").trim();if(/^(https?:|mailto:)/i.test(s))return s;if(/^[a-z][a-z0-9+.-]*:/i.test(s)||s.startsWith("//"))return "#";return s;}
function kindOf(task){task=task||"";if(task.includes("【小必做】")||task.includes("【小必做·"))return "must";if(task.includes("【可选】")||task.includes("【可选·"))return "opt";return "";}
$("#cd").textContent=countdown();
function tasks(sub,w,day){const sw=(S[sub].weeks||[]).find(x=>x.week===w.week);if(!sw)return[];
 return [...(sw.weekday||[]),...(sw.weekend||[])].filter(t=>!day||t.day===day).map(t=>({...t,sub,key:`${w.week}|${sub}|${t.day}|${t.task}`}))}
function li(t){const k=kindOf(t.task);const label=k==="must"?"小必做":k==="opt"?"可选":"任务";
 return `<article class="card ${k} ${done[t.key]?"done":""}"><div class="row"><label class="hit"><input type="checkbox" aria-label="完成" data-k="${encodeURIComponent(t.key)}" ${done[t.key]?"checked":""}></label><div class="main-col"><div class="tags"><span class="tag">${esc(t.sub)}</span><span class="tag">${esc(t.day)}</span>${t.slot?`<span class="tag">${esc(t.slot)}</span>`:""}<span class="tag">${esc(t.min||"")}分</span>${t.type?`<span class="tag">${esc(t.type)}</span>`:""}<span class="tag ${k}">${label}</span></div><details open><summary>${esc(label)} · ${esc(t.day)} · ${esc(t.min||"")}分</summary><div class="task">${esc(t.task||"")}</div></details></div></div></article>`}
function weekHead(sub,w){const sw=(S[sub].weeks||[]).find(x=>x.week===w.week);return sw?`<div class="card"><b>${esc(sub)}</b> · ${esc(sw.topic||"")}<br><small>目标：${esc(sw.goal||"")}　自测：${esc(sw.check||"")}</small></div>`:""}
const V={
 today(){const d=studyDate(),w=weekOf(d),day=DN[d.getUTCDay()];if(!w)return `<p>${iso(d)} ${day}（北京时间，04:00换日）</p><div class="card">${iso(d)<C.start?"计划尚未开始，可先查看「本周」预览首周。":"本轮计划已结束，可在「本周」回顾，不再分配当天任务。"}</div>`;let h=`<p>第${w.week}周 · ${esc(phaseName(w.phase))} · ${iso(d)} ${day} ${esc(w.note||"")}</p>`;
  for(const s in S)h+=tasks(s,w,day).map(li).join("");return h||"暂无任务"},
 week(wk){const w=wk||weekOf(studyDate())||(iso(studyDate())<C.start?C.weeks[0]:C.weeks[C.weeks.length-1]);let h=`<select id="ws">${C.weeks.map(x=>`<option value="${x.week}" ${x.week===w.week?"selected":""}>第${x.week}周 ${x.monday} ${esc(phaseName(x.phase))}</option>`).join("")}</select>`;
  for(const s in S){h+=weekHead(s,w);h+=tasks(s,w).map(li).join("")}return h},
 all(){let h='<div class="table-scroll"><table><tr><th>周</th><th>阶段</th>'+Object.keys(S).map(s=>`<th>${esc(s)}</th>`).join("")+"</tr>";
  for(const w of C.weeks)h+=`<tr><td>${w.week}<br><small>${w.monday}</small></td><td><small>${esc(phaseName(w.phase))}${w.note?"<br>"+esc(w.note):""}</small></td>`+Object.keys(S).map(s=>{const x=(S[s].weeks||[]).find(y=>y.week===w.week);return `<td>${x?esc(x.topic):""}</td>`}).join("")+"</tr>";return h+"</table></div>"},
 subj(){return Object.values(S).map(s=>`<div class="card"><h3>${esc(s.subject)}</h3>${(s.knowledge||[]).map(k=>`<details><summary>${esc(k.topic)}</summary><b>知识点</b><ul>${(k.points||[]).map(p=>`<li>${esc(p)}</li>`).join("")}</ul><b>做题技巧</b><ul>${(k.skills||[]).map(p=>`<li>${esc(p)}</li>`).join("")}</ul></details>`).join("")}${(s.resources||[]).length?"<b>资源</b><ul>"+s.resources.map(r=>`<li><a href="${esc(safeUrl(r.url))}">${esc(r.name)}</a> ${esc(r.note||"")}</li>`).join("")+"</ul>":""}</div>`).join("")}
};
let cur="today";function go(v,arg){cur=v;document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("on",b.dataset.v===v));
 let html=V[v](arg);if(!storageOK)html='<p id="storageWarning" class="warn">浏览器存储不可用：当前勾选仅本次有效，刷新后可能丢失。</p>'+html;app.innerHTML=html;
 const ws=$("#ws");if(ws)ws.onchange=()=>go("week",C.weeks.find(x=>x.week==ws.value))}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>go(b.dataset.v));
app.addEventListener("change",e=>{const k=e.target.dataset&&e.target.dataset.k;if(!k)return;const key=decodeURIComponent(k);e.target.checked?done[key]=1:delete done[key];save();if(!storageOK&&!$("#storageWarning")){app.insertAdjacentHTML("afterbegin",'<p id="storageWarning" class="warn">浏览器存储不可用：当前勾选仅本次有效，刷新后可能丢失。</p>');}const card=e.target.closest(".card");if(card)card.classList.toggle("done",e.target.checked)});
go("today");
