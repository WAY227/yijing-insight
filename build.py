# -*- coding: utf-8 -*-
# Build index.html by injecting hexagrams.min.json into the template.
import io, os

HERE = os.path.dirname(os.path.abspath(__file__))
hx = open(os.path.join(HERE, "hexagrams2.min.json"), encoding="utf-8").read()

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>易经灵占 · YI JING INSIGHT</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&display=swap" rel="stylesheet">
<style>
  body { font-family: 'Noto Serif SC', 'Cormorant Garamond', serif; }
  .en { font-family: 'Cormorant Garamond', serif; }
  .fade-in { animation: fadein .8s ease both; }
  @keyframes fadein { from { opacity:0; transform: translateX(16px);} to { opacity:1; transform:none; } }
  .anim-bar { animation: grow .5s ease-out both; transform-origin: center; }
  @keyframes grow { from { opacity:0; transform: scaleX(0);} to { opacity:1; transform: scaleX(1);} }
  .markdown-body h1,.markdown-body h2 { color:#fff; border-bottom:1px solid rgba(255,255,255,.1); padding-bottom:.3em; }
  .markdown-body h3 { color:#C5A059; }
  .markdown-body h4 { color:#C5A059; }
  .markdown-body p { margin:.6em 0; line-height:1.9; }
  .markdown-body ul { margin:.6em 0; padding-left:1.4em; list-style:disc; }
  .markdown-body li { margin:.25em 0; line-height:1.8; }
  .markdown-body strong { color:#C5A059; font-weight:600; }
  .markdown-body blockquote { border-left:2px solid #C5A059; padding-left:1em; color:rgba(255,255,255,.65); margin:.8em 0; }
  ::-webkit-scrollbar { width:6px; } ::-webkit-scrollbar-thumb { background:rgba(197,160,89,.3); }
</style>
</head>
<body class="bg-[#0A0A0B]">
<div id="root"></div>
<script>
const HEX = __HEX_DATA__;
const BY_BIN = Object.fromEntries(HEX.map(h=>[h.b,h]));
const TRI_NAME = {"111":"乾","000":"坤","100":"震","010":"坎","001":"艮","110":"兑","101":"离","011":"巽"};
const TRI_SYM  = {"111":"☰","000":"☷","100":"☳","010":"☵","001":"☶","110":"☱","101":"☲","011":"☴"};
const WUXING = ["Metal","Wood","Water","Fire","Earth"];
const AI_MODEL_CANDIDATES = ["gemini-3.5-flash","gemini-3.5-flash-lite","gemini-3.7-flash","gemini-flash-latest"];
const DIRECT_MODEL_CANDIDATES = ["gemini-3.5-flash-lite","gemini-3.5-flash"];
// 三枚铜钱四象：字面数=2，背面数=3，三枚之和 6/7/8/9
// 6=老阴(变) 7=少阳 8=少阴 9=老阳(变)
const YAO_META = {
  6: {yang:0, moving:true,  name:"老阴", mark:" metamorph ▾ ", cn:"⚏", coin:"背背背"},
  7: {yang:1, moving:false, name:"少阳", mark:"", coin:""},
  8: {yang:0, moving:false, name:"少阴", mark:"", coin:""},
  9: {yang:1, moving:true,  name:"老阳", mark:" metamorph ▴ ", cn:"⚊", coin:"字字字"}
};
const YAO_LABEL = ["上","五","四","三","二","初"]; // display index 0..5 top->bottom
function yaoLabel(pos){ // pos 1..6 bottom->top
  return pos===6 ? "上爻" : "第" + ["","二","三","四","五"][pos] + "爻";
}

// ---------- state ----------
// vals: 爻值 6-9 自下而上；hex: 本卦；zhiHex: 之卦（有变爻时）
const S = { phase:"IDLE", question:"", vals:[], lines:[], interp:"", error:"", hex:null, zhiHex:null, aiUsed:false, movingPos:[] };
const root = document.getElementById("root");
const esc = (s) => String(s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

// 朱熹《易学启蒙》变爻取辞规则
function zhuxiRule(moving) {
  const n = moving.length;
  if (n === 0) return { text:"六爻皆不变，以本卦卦辞断之。", take:"gua" };
  if (n === 1) return { text:"一爻动，以本卦动爻爻辞断之。", take:"ben" };
  if (n === 2) return { text:"二爻动，以本卦二动爻爻辞为主，上爻为重。", take:"ben" };
  if (n === 3) return { text:"三爻动，以本卦及之卦的卦辞合断，本卦为贞（体），之卦为悔（用）。", take:"both" };
  if (n === 4) return { text:"四爻动，以之卦二不动爻爻辞断之，以下爻为主。", take:"zhiStatic" };
  if (n === 5) return { text:"五爻动，以之卦不动的那一爻爻辞断之。", take:"zhiStatic" };
  return { text:"六爻全动（乾坤有「用九／用六」者以用辞断），以之卦卦辞断之。", take:"all" };
}

// ---------- ganzhi (real dates) ----------
function ganzhi() {
  const now = new Date();
  const y = now.getFullYear(), m = now.getMonth()+1, d = now.getDate();
  const starts = [[2,4],[3,6],[4,5],[5,6],[6,6],[7,7],[8,8],[9,8],[10,8],[11,7],[12,7]];
  const branches = ["寅","卯","辰","巳","午","未","申","酉","戌","亥","子","丑"];
  let bi = 11; // 丑: Dec 7 - Feb 3
  for (let i=0;i<starts.length;i++){ const [sm,sd]=starts[i];
    if (m>sm || (m===sm && d>=sd)) bi=i; }
  const mb = branches[bi];
  const stems="甲乙丙丁戊己庚辛壬癸", br6="子丑寅卯辰巳午未申酉戌亥";
  const yb = br6[((y-4)%12+12)%12], ys = stems[((y-4)%10+10)%10];
  const jdn = Math.floor(now.getTime()/86400000 + 2440588);
  const di = ((jdn+49)%60+60)%60;
  const ds = stems[di%10], db = br6[di%12];
  const seasons = ["Spring Phase","Summer Phase","Autumn Phase","Winter Phase"];
  let season = seasons[3]; if (m>=3&&m<=5) season=seasons[0]; else if (m>=6&&m<=8) season=seasons[1]; else if (m>=9&&m<=11) season=seasons[2];
  const ds2 = y + "." + String(m).padStart(2,"0") + "." + String(d).padStart(2,"0");
  return { yz: ys+yb+"年 · "+mb+"月 · "+ds+db+"日", dt: ds2+" — "+season };
}

// ---------- traditional (offline) interpretation ----------
function localReading(hex, zhiHex, moving) {
  const rule = zhuxiRule(moving);
  const nY = hex.b.split("").filter(c=>c==="1").length;
  const trend = nY>=4 ? "阳盛而动，宜进取开拓" : nY<=2 ? "阴柔蓄势，宜守成待时" : "阴阳相济，进退有度";
  let sec = "### " + hex.z + "卦 · " + hex.en + "（第" + hex.n + "卦）\n\n"
    + "**卦象**：上" + hex.up.replace(/[乾坤震坎艮兑离巽]/, "") + "下" + hex.low.replace(/[乾坤震坎艮兑离巽]/, "")
    + " · 六爻阳" + nY + "阴" + (6-nY) + "\n\n"
    + "**卦辞**：" + hex.g + "\n\n";
  if (moving.length) {
    sec += "**动爻**：" + moving.map(p=>"第" + p + "爻").join("、") + "（" + rule.text + "）\n\n";
    const cn = {1:"初",2:"二",3:"三",4:"四",5:"五",6:"上"};
    for (const p of moving.slice(0,2)) {
      const key = "l" + (7-p);
      const yy = hex.y[key];
      if (yy) sec += "> **" + cn[p] + "爻爻辞**：" + yy + "\n>\n";
    }
    if (zhiHex) sec += "**之卦**：" + zhiHex.z + "卦（第" + zhiHex.n + "卦）——" + zhiHex.g + "\n\n";
  }
  sec += "#### 卦意浅释\n"
    + hex.z + "之象，" + trend + "。所问之事当以" + (nY>=4?"果决行之，然防过亢":"沉潜蓄力，勿躁进") + "为要。\n\n"
    + (zhiHex ? "本卦" + hex.z + "变而为" + zhiHex.z + "，事有转向之机：始则" + hex.z + "，终则" + zhiHex.z + "。\n\n" : "")
    + "#### 行动建议\n"
    + "- **近期**：" + (nY>=4?"乘势而上，但留三分余地":"稳字当头，先修内功") + "\n"
    + "- **中期**：" + (hex.n<=20?"根基已固，徐图展开":hex.n<=42?"中道而行，防盈防满":"事将成，慎终如始") + "\n"
    + "- **忌**：" + (hex.n%2===0?"与人争执，意气用事":"贪功冒进，见利忘义") + "\n\n"
    + "---\n\n*本地断卦 · 仅供参考。如需 AI 深度解读，请点击右上角设置 Gemini API Key。*";
  return sec;
}

// ---------- Gemini call ----------
// 路径1: 本地中转 /api/divine（server.py，走系统代理，推荐）
// 路径2: 浏览器直连 Google（需浏览器能翻出去）
// 都失败则抛错，由调用方退回本地断卦
async function geminiInterpretation(question, hex, zhiHex, moving, vals) {
  const key = (localStorage.getItem("GEMINI_API_KEY")||"").trim();
  if (!key) throw { noKey: true };
  const rule = zhuxiRule(moving);
  const cn = {1:"初",2:"二",3:"三",4:"四",5:"五",6:"上"};
  const sys = "你是精通《周易》与朱熹《易学启蒙》变占法的断卦师，文风古雅而切中人心。"
    + "用户以三枚铜钱法起得本卦" + hex.z + "卦（第" + hex.n + "卦，上" + hex.up + "下" + hex.low + "），卦辞：「" + hex.g + "」。"
    + (moving.length ? "动爻在第" + moving.join("、") + "爻，动爻爻辞：" + moving.map(p=>"「" + cn[p] + "爻：" + (hex.y["l"+(7-p)]||"") + "」").join("；") + "。"
       + (zhiHex ? "之卦为" + zhiHex.z + "卦（第" + zhiHex.n + "卦），卦辞：「" + zhiHex.g + "」。" : "")
       + "取断规则：" + rule.text : "六爻皆不变，以本卦卦辞断之。")
    + "请用 markdown 输出，结构如下：一、卦象总览（本卦大势）；"
    + (moving.length ? "二、动爻详解（引动爻爻辞原文，逐爻阐发其机）；" : "二、卦辞详解；")
    + (zhiHex ? "三、之卦展望（事之归趋）；" : "三、时机与变数；")
    + "四、行动建议（三条，短句，可执行）。全文 450 字以内，不要开场白与免责声明，结尾以一句古风短语收束。";
  const userQ = "所问之事：「" + (question || "今日运势") + "」。"
    + "起卦详情：自下而上爻值为 " + vals.join(",") + "（6老阴7少阳8少阴9老阳），"
    + "本卦" + hex.z + (moving.length ? "，动" + moving.length + "爻" : "，六爻皆静") + (zhiHex ? "，变" + zhiHex.z + "卦。" : "。")
    + "请依上述规则解卦。";
  const payload = { apiKey: key, question: userQ, hexagramLines: vals, moving: moving,
                    meta: { ben: hex.n, zhi: zhiHex ? zhiHex.n : null, rule: rule.text, sys: sys } };
  // 路径1：本地中转
  try {
    const ctrl = new AbortController();
    const kill = setTimeout(() => ctrl.abort("timeout"), 60000);
    const res = await fetch("/api/divine", {
      method:"POST", headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload), signal: ctrl.signal
    });
    clearTimeout(kill);
    const data = await res.json().catch(()=>({}));
    if (res.ok && data.interpretation) return data.interpretation;
    throw new Error(data.error || ("中转服务 " + res.status));
  } catch(e) {
    if (e && e.name === "AbortError") throw new Error("中转服务超时");
    if (!String(e.message||"").includes("Failed to fetch") || location.protocol === "http:" && await serverAlive()) throw e;
  }
  // 路径2：浏览器直连（仅当中转不可达）
  const body = {
    systemInstruction: { parts: [{ text: sys }] },
    contents: [{ role:"user", parts: [{ text: userQ }] }],
    generationConfig: { temperature: 0.9 }
  };
  let lastErr = null;
  for (const model of DIRECT_MODEL_CANDIDATES) {
    const ctrl = new AbortController();
    const kill = setTimeout(() => ctrl.abort("timeout"), 20000);
    try {
      const res = await fetch("https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent", {
        method:"POST", headers:{ "Content-Type":"application/json", "x-goog-api-key": key },
        body: JSON.stringify(body), signal: ctrl.signal
      });
      clearTimeout(kill);
      if (!res.ok) {
        const t = await res.text();
        lastErr = new Error("API " + res.status + ": " + t.slice(0,160));
        continue;
      }
      const data = await res.json();
      const text = (data.candidates && data.candidates[0] && data.candidates[0].content && data.candidates[0].content.parts || []).map(p=>p.text||"").join("");
      if (!text) throw new Error("AI 返回为空");
      return text;
    } catch(e) { clearTimeout(kill); lastErr = e; }
  }
  throw lastErr || new Error("AI 调用失败");
}

async function serverAlive() {
  try {
    const r = await fetch("/healthz", { signal: AbortSignal.timeout ? AbortSignal.timeout(3000) : undefined });
    return r.ok;
  } catch(e) { return false; }
}

// ---------- render ----------
function frame(inner) {
  const g = ganzhi();
  return '<div class="h-screen w-full flex flex-col bg-[#0A0A0B] text-[#D1D1C7] overflow-hidden select-none">'
  +'<header class="flex justify-between items-center px-6 md:px-10 py-6 border-b border-white/5 shrink-0 z-20 bg-[#0A0A0B]">'
  +'<div class="flex items-center gap-4">'
  +'<div class="w-10 h-10 border border-[#C5A059] flex items-center justify-center text-[#C5A059] text-xl font-bold italic shadow-[0_0_15px_rgba(197,160,89,0.2)]">易</div>'
  +'<div><h1 class="text-xl font-semibold tracking-widest text-white">易经灵占 · YI JING INSIGHT</h1>'
  +'<p class="text-[10px] uppercase tracking-[0.2em] text-[#C5A059]/80 hidden sm:block en">Traditional Wisdom x Modern Decision</p></div></div>'
  +'<div class="text-right hidden sm:flex flex-col items-end gap-1">'
  +'<p class="text-sm text-white/60">'+g.yz+'</p>'
  +'<p class="text-[10px] text-[#C5A059] uppercase tracking-tighter en">'+g.dt+'</p>'
  +'<button id="btnSettings" class="text-[10px] tracking-widest text-white/40 hover:text-[#C5A059] uppercase border border-white/10 hover:border-[#C5A059]/50 px-3 py-1 transition-all en">'
  +((localStorage.getItem("GEMINI_API_KEY")||"").trim()?"AI 玄机 · 已启":"AI 玄机 · 设置 Key")+'</button></div></header>'
  +'<main class="flex-1 flex flex-col md:flex-row overflow-hidden relative z-10">'+inner+'</main>'
  +'<footer class="h-12 border-t border-white/5 px-6 md:px-10 flex justify-between items-center text-[10px] tracking-widest text-white/40 uppercase bg-[#080809] shrink-0 z-20 en">'
  +'<div class="flex gap-4 md:gap-8"><span class="hidden sm:inline">Status: Syncing with Celestial Nodes</span><span>Node ID: 0xFF-64-QI</span></div>'
  +'<div class="flex gap-4"><span class="text-[#C5A059]">Hexagram Index: '+(S.hex?String(S.hex.n).padStart(2,"0"):"--")+'/64</span><span>Insight Engine v4.2.0 · Clone</span></div></footer></div>';
}

function hexView(vals, phase) {
  const rev = [...vals].reverse(); // display top->bottom
  let rows = "";
  for (let i=0;i<6;i++) {
    const v = rev[i];
    if (v===undefined) {
      rows += '<div class="w-full h-5 md:h-6 flex items-center justify-center"><div class="w-full h-full bg-white/5 rounded-sm animate-pulse"></div></div>';
    } else {
      const meta = YAO_META[v], yang = meta.yang;
      const bar = yang
        ? '<div class="w-full h-full bg-[#C5A059] rounded-sm shadow-[0_0_20px_rgba(197,160,89,0.15)] anim-bar"></div>'
        : '<div class="w-full h-full flex justify-between"><div class="w-[45%] h-full bg-[#C5A059] rounded-sm shadow-[0_0_20px_rgba(197,160,89,0.15)] anim-bar"></div><div class="w-[45%] h-full bg-[#C5A059] rounded-sm shadow-[0_0_20px_rgba(197,160,89,0.15)] anim-bar"></div></div>';
      const dot = meta.moving ? '<div class="absolute -right-8 top-1/2 -translate-y-1/2 text-rose-400 text-xs tracking-widest animate-pulse whitespace-nowrap">'+(v===9?"老阳○":"老阴×")+'</div>' : "";
      rows += '<div class="relative w-full h-5 md:h-6 flex">'+bar+dot+'</div>';
    }
  }
  return '<div class="flex flex-col items-center gap-2.5 md:gap-3.5 w-40 md:w-56 mx-auto">'+rows+'</div>';
}

// 掷币过程文字（三枚铜钱每掷）
function coinLogText(vals) {
  if (!vals.length) return "";
  const last = vals[vals.length-1];
  const pos = vals.length;
  const names = {6:"老阴 ⚋⚋ 变",7:"少阳 ⚊",8:"少阴 ⚋",9:"老阳 ⚊ 变"};
  return '<div class="mt-3 text-[11px] text-white/45 tracking-wider text-center">初' + ["","初爻","二爻","三爻","四爻","五爻","上爻"][pos] + '：掷得 <span class="text-[#C5A059]">' + names[last] + '</span></div>';
}

function leftPane() {
  if (S.phase==="IDLE") {
    return '<section class="flex flex-col items-center justify-center p-8 md:p-12 bg-gradient-to-b from-[#0F0F11] to-[#0A0A0B] md:w-[46%] shrink-0 w-full">'
    +'<div class="mb-8 text-center"><span class="text-[#C5A059] text-xs uppercase tracking-[0.3em] block mb-2 en">Enter Query</span>'
    +'<h2 class="font-bold text-white tracking-tighter text-4xl md:text-5xl">请示神谕</h2>'
    +'<p class="text-[#C5A059] italic mt-2 text-sm md:text-base en">Seek the Wisdom</p></div>'
    +'<div class="min-h-[200px] flex items-center justify-center w-full mb-8 md:mb-12"><div class="w-full max-w-sm flex flex-col gap-8 items-center">'
    +'<input id="q" placeholder="你心中的疑问是什么？（留空看运势）" class="w-full bg-transparent border-b border-white/20 text-center py-3 px-4 focus:outline-none focus:border-[#C5A059] transition-colors placeholder:text-white/30 text-white" type="text">'
    +'<button id="btnCast" class="px-8 py-3 bg-transparent border border-[#C5A059]/40 text-[#C5A059] text-sm tracking-widest hover:bg-[#C5A059] hover:text-black transition-all mx-auto uppercase en">Start New Divination</button>'
    +(S.error?'<p class="text-rose-500 text-sm mt-4 text-center">'+esc(S.error)+'</p>':"")
    +'</div></div></section>'
    +'<section class="flex-1 hidden md:flex items-center justify-center bg-[#0C0C0E]"><div class="text-center space-y-3 opacity-70">'
    +'<div class="text-6xl text-[#C5A059]/90 font-bold">易</div>'
    +'<p class="text-[10px] tracking-[0.3em] text-white/40 uppercase en">六十四卦 · 384 爻 · 尽在指尖</p>'
    +'<p class="text-[10px] tracking-[0.2em] text-white/25 uppercase en">Cosmic Cache: '+HEX.length+' Hexagrams Loaded</p></div></section>';
  }
  const title = S.phase==="RESULT"?"卦象已成":"掷钱起卦...";
  const sub = S.phase==="RESULT"?(S.hex.z+" · "+S.hex.p):"Tossing the Coins";
  const movingStr = S.movingPos.length ? " · 动" + S.movingPos.length + "爻" : " · 六爻皆静";
  return '<section class="flex flex-col items-center justify-start p-8 md:p-12 bg-gradient-to-b from-[#0F0F11] to-[#0A0A0B] md:w-[46%] shrink-0 w-full overflow-y-auto">'
  +'<div class="mb-6 text-center"><span class="text-[#C5A059] text-xs uppercase tracking-[0.3em] block mb-2 en">Current Manifestation</span>'
  +'<h2 class="font-bold text-white tracking-tighter text-3xl md:text-4xl '+(S.phase==="RESULT"?"":"animate-pulse")+'">'+title+'</h2>'
  +'<p class="text-[#C5A059] italic mt-2 text-sm md:text-base en">'+sub+'</p></div>'
  +'<div class="flex items-center justify-center w-full mb-4"><div class="w-full max-w-sm flex flex-col items-center">'
  +hexView(S.vals, S.phase)
  +(S.phase==="CASTING"?coinLogText(S.vals):"")
  +(S.phase==="RESULT" && S.hex ?
    '<div class="text-center mt-5"><div class="text-2xl font-bold text-white tracking-widest">'+S.hex.z+(S.zhiHex?'<span class="text-[#C5A059] text-lg mx-2">→</span>'+S.zhiHex.z:"")+'</div>'
    +'<div class="text-xs text-[#C5A059] tracking-[0.25em] mt-1 uppercase en">HEXAGRAM No.'+String(S.hex.n).padStart(2,"0")+' / 64'+(S.zhiHex?' → No.'+String(S.zhiHex.n).padStart(2,"0"):"")+'</div>'
    +'<div class="text-sm text-white/70 mt-1">上卦 '+S.hex.up.slice(1)+TRI_SYM[S.hex.b.slice(3)]+' · 下卦 '+S.hex.low.slice(1)+TRI_SYM[S.hex.b.slice(0,3)]+movingStr+'</div>'
    +(S.movingPos.length?'<div class="text-xs text-rose-400/90 mt-1 tracking-wider">动爻：第 '+S.movingPos.join("、")+' 爻</div>':"")
    +'</div>'
    +'<div class="flex flex-col gap-3 mt-3 w-full max-w-[220px]">'
    +'<button id="btnSave" class="px-8 py-3 bg-[#C5A059] text-black text-sm tracking-widest hover:bg-white transition-all uppercase en">Save Result</button>'
    +'<button id="btnReset" class="px-8 py-3 bg-transparent border border-[#C5A059]/40 text-[#C5A059] text-sm tracking-widest hover:bg-[#C5A059] hover:text-black transition-all uppercase en">Reset Divination</button></div>'
    :"")
  +'</div></div></section>';
}

function rightPane() {
  if (S.phase==="IDLE") return "";
  if (S.phase==="ANALYZING") return '<section class="flex-1 flex flex-col p-6 md:p-12 bg-[#0C0C0E] overflow-y-auto">'
    +'<div class="flex-1 flex flex-col items-center justify-center text-[#C5A059] space-y-4">'
    +'<svg class="w-8 h-8 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56" stroke-linecap="round"/></svg>'
    +'<p class="tracking-widest text-sm animate-pulse uppercase en">Syncing with Celestial Nodes...</p>'
    +'<p class="text-[10px] tracking-widest text-white/30 uppercase">'+((localStorage.getItem("GEMINI_API_KEY")||"").trim()?"Gemini 玄机推演中":"本地断卦引擎推演中")+'</p></div></section>';
  return '<section class="flex-1 flex flex-col p-6 md:p-12 bg-[#0C0C0E] overflow-y-auto">'
    +'<div class="flex-1 flex flex-col max-w-3xl mx-auto w-full fade-in">'
    +'<div id="resultCard" class="w-full flex flex-col pb-8 px-4 sm:px-8 bg-[#0C0C0E]">'
    +'<div class="flex flex-col sm:flex-row gap-6 mb-10 shrink-0">'
    +'<div class="flex-1 p-6 bg-white/5 border border-white/10 rounded-sm">'
    +'<h4 class="text-[10px] uppercase tracking-widest text-[#C5A059] mb-4 en">所问之事 · Inquiry</h4>'
    +'<div class="flex items-baseline gap-2"><span class="text-2xl md:text-3xl font-light text-white truncate max-w-[200px] md:max-w-[300px] block">'+esc(S.question||"今日运势")+'</span></div>'
    +'<div class="mt-4 h-1 w-full bg-white/10"><div class="h-full bg-[#C5A059] w-full"></div></div></div>'
    +'<div class="flex-1 p-6 bg-white/5 border border-white/10 rounded-sm hidden sm:block">'
    +'<h4 class="text-[10px] uppercase tracking-widest text-[#C5A059] mb-4 en">五行能量 · Elemental Flow</h4>'
    +'<div class="flex justify-between items-end h-10 gap-2">'
    +[80,30,45,60,20].map((h,i)=>'<div class="w-full '+(i===0?"bg-[#C5A059]":"bg-white/20")+'" style="height:'+h+'%"></div>').join("")
    +'</div><div class="flex justify-between text-[8px] mt-2 opacity-40 uppercase tracking-tighter en">'
    +WUXING.map(w=>"<span>"+w+"</span>").join("")+'</div></div></div>'
    +'<div class="flex-1 space-y-8"><div class="markdown-body text-[15px] text-white/85">'+marked.parse(S.interp)+'</div>'
    +'<div class="pt-8 border-t border-white/5 mt-12 pb-4">'
    +'<p class="text-[10px] italic text-white/30 text-center en">&ldquo;天行健，君子以自强不息。&rdquo; &mdash; As Heaven&#39;s movement is ever vigorous, so must a leader strive for continuous self-improvement.</p>'
    +'</div></div></div></div></section>';
}

function render() {
  root.innerHTML = frame(leftPane() + rightPane());
  bind();
}

function bind() {
  const bc = document.getElementById("btnCast");
  if (bc) {
    const qi = document.getElementById("q");
    const start = () => startCasting(qi ? qi.value : "");
    bc.onclick = start;
    if (qi) qi.onkeydown = (e) => { if (e.key==="Enter") { e.preventDefault(); start(); } };
  }
  const br = document.getElementById("btnReset");
  if (br) br.onclick = () => { S.phase="IDLE"; S.vals=[]; S.lines=[]; S.interp=""; S.error=""; S.hex=null; S.zhiHex=null; S.movingPos=[]; render(); };
  const bs = document.getElementById("btnSave");
  if (bs) bs.onclick = savePDF;
  const st = document.getElementById("btnSettings");
  if (st) st.onclick = openSettings;
}

// ---------- flow ----------
// 三枚铜钱：字(阴面)=2，背(阳面)=3，三枚合计 6/7/8/9
function tossCoins() {
  let sum = 0;
  for (let i=0;i<3;i++) sum += Math.random() < 0.5 ? 2 : 3;
  return sum; // 6:老阴 7:少阳 8:少阴 9:老阳
}

function startCasting(question) {
  S.phase="CASTING"; S.question=question.trim();
  S.vals=[]; S.lines=[]; S.interp=""; S.error=""; S.hex=null; S.zhiHex=null; S.movingPos=[];
  render();
  const M = [];
  const timer = setInterval(() => {
    if (M.length < 6) {
      M.push(tossCoins());
      S.vals = [...M];
      render();
    } else {
      clearInterval(timer);
      settle(M);
    }
  }, 700);
}

function settle(vals) {
  // 本卦：7,9 阳爻；6,8 阴爻
  const lines = vals.map(v => YAO_META[v].yang ? 1 : 0);
  S.lines = lines;
  S.hex = BY_BIN[lines.join("")] || HEX[0];
  // 变爻位置（1..6）
  S.movingPos = vals.map((v,i)=>YAO_META[v].moving ? i+1 : 0).filter(x=>x);
  // 之卦：动爻阴阳互变
  if (S.movingPos.length) {
    const zlines = lines.map((y,i)=>S.movingPos.includes(i+1) ? (y?0:1) : y);
    S.zhiHex = BY_BIN[zlines.join("")] || null;
  } else S.zhiHex = null;
  analyze(vals);
}

async function analyze(vals) {
  S.phase="ANALYZING"; render();
  try {
    const text = await geminiInterpretation(S.question, S.hex, S.zhiHex, S.movingPos, vals);
    S.interp = text; S.aiUsed = true;
  } catch(e) {
    if (e && e.noKey) { S.interp = localReading(S.hex, S.zhiHex, S.movingPos); S.aiUsed = false; }
    else {
      const msg = String((e && e.message) || e).replace(/</g,"&lt;");
      S.interp = localReading(S.hex, S.zhiHex, S.movingPos) + "\n\n---\n\n*⚠️ AI 玄机未达（" + msg + "），已退回本地断卦。*";
      S.aiUsed = false;
    }
  }
  S.phase = "RESULT"; render(); scrollToResult();
}
function scrollToResult(){ const c=document.getElementById("resultCard"); if(c) c.scrollIntoView({behavior:"smooth"}); }

async function savePDF() {
  const card = document.getElementById("resultCard");
  if (!card) return;
  try {
    const canvas = await html2canvas(card, { quality:0.95, backgroundColor:"#0C0C0E", scale:2 });
    const img = canvas.toDataURL("image/jpeg", 0.95);
    const w = canvas.width, h = canvas.height;
    const { jsPDF } = await import("https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js");
    const doc = new jsPDF({ orientation: w>h?"landscape":"portrait", unit:"px", format:[w,h] });
    doc.addImage(img, "JPEG", 0, 0, w, h);
    doc.save("神谕占卜_" + new Date().toISOString().slice(0,10) + ".pdf");
  } catch(e) { alert("导出PDF失败，请重试。"); }
}

function openSettings() {
  const cur = localStorage.getItem("GEMINI_API_KEY")||"";
  const overlay = document.createElement("div");
  overlay.className = "fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4";
  overlay.innerHTML = '<div class="w-full max-w-md bg-[#101012] border border-[#C5A059]/30 p-8 rounded-sm space-y-5">'
    +'<h3 class="text-white tracking-widest text-lg">启 · AI 玄机</h3>'
    +'<p class="text-xs text-white/50 leading-relaxed">填入你自己的 <span class="text-[#C5A059]">Gemini API Key</span>（<a class="underline text-[#C5A059]" href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a> 免费领取）。Key 仅保存在本机浏览器，解读请求由你的浏览器直达 Google，每日额度吃你自己的免费配额。不填则使用内置《周易》本地断卦。</p>'
    +'<input id="keyInput" type="password" value="'+esc(cur)+'" placeholder="AIza..." class="w-full bg-transparent border-b border-white/20 py-3 px-1 focus:outline-none focus:border-[#C5A059] text-white text-sm">'
    +'<div class="flex gap-3 justify-end flex-wrap">'
    +'<button id="kClear" class="px-4 py-2 text-xs tracking-widest text-white/50 hover:text-white uppercase border border-white/10">清除</button>'
    +'<button id="kSave" class="px-6 py-2 text-xs tracking-widest bg-[#C5A059] text-black hover:bg-white uppercase">保存并启用</button>'
    +'<button id="kClose" class="px-4 py-2 text-xs tracking-widest text-[#C5A059] hover:text-white uppercase">关闭</button></div></div>';
  document.body.appendChild(overlay);
  overlay.querySelector("#kSave").onclick = () => { localStorage.setItem("GEMINI_API_KEY", overlay.querySelector("#keyInput").value.trim()); overlay.remove(); render(); };
  overlay.querySelector("#kClear").onclick = () => { localStorage.removeItem("GEMINI_API_KEY"); overlay.remove(); render(); };
  overlay.querySelector("#kClose").onclick = () => overlay.remove();
}

render();
</script>
</body>
</html>'''

html = TEMPLATE.replace("__HEX_DATA__", hx)
out = os.path.join(HERE, "index.html")
with io.open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("index.html written:", len(html), "chars")
