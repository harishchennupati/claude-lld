import sys,json,html,pathlib
sys.path.insert(0,"/Users/harishchennupati/answers/lld")
from _primer_data import CARDS
SECS={"A":("Java for LLD rounds","The language features every machine-coding solution is made of. Enums, interfaces, records, equals/hashCode, collections. If these are slow under your fingers, the 60 minutes are gone before the design starts."),
      "B":("Concurrency","The ten primitives that answer 'is this thread-safe?'. Every LLD has one invariant that breaks under two threads; these are the tools, and the sentence to say when you pick one."),
      "C":("SOLID, as before/after code","Five principles, each shown as the violation and the fix. You will be asked to map them to your design -- the answer is a class name, not a definition."),
      "D":("Design patterns, as pain then shape","Twelve patterns you will actually use. Each opens with the sentence that triggers it, because a pattern named before its pain is a red flag."),
      "E":("Principles beyond SOLID","Composition, encapsulation, idempotency, YAGNI, and how to end a round: 'here is how I would test it'.")}
def esc(s): return html.escape(s)
cards_html=[]
for c in CARDS:
    cards_html.append(f'''<details class="card" id="{c['id']}" data-sec="{c['sec']}" data-name="{esc(c['name'].lower())}">
<summary><span class="nm">{esc(c['name'])}</span><span class="one">{esc(c['one'])}</span><label class="miss" title="mark as missed"><input type="checkbox" data-miss="{c['id']}"> missed</label></summary>
<div class="body">
<p class="tell">{c['tell']}</p>
<div class="ed"><div class="tab">the idiom -- compiled on OpenJDK 26</div><pre><code class="java">{esc(c['code'])}</code></pre></div>
<p class="mistake"><b>The mistake they catch:</b> {esc(c['mistake'])}</p>
<p class="say"><b>Say:</b> {esc(c['say'])}</p>
</div></details>''')
by_sec={k:[] for k in SECS}
for c,h in zip(CARDS,cards_html): by_sec[c['sec']].append(h)
sections="".join(f'<section class="sec" id="sec{k}"><h2><span>{k}</span>{esc(t)}</h2><p class="lede">{esc(d)}</p>{"".join(by_sec[k])}</section>' for k,(t,d) in SECS.items())
drill=json.dumps([{"id":c["id"],"name":c["name"],"one":c["one"],"sec":c["sec"]} for c in CARDS])
page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Java primer for LLD rounds</title>
<style>
:root{{--bg:#0f1419;--bg2:#161b22;--bg3:#1c2330;--line:#2a3441;--text:#d6dde6;--muted:#7d8896;--acc:#3ddbb0;--acc2:#7cc4ff;--warn:#f0a35e;--err:#ff6b6b;--mono:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;--ui:-apple-system,"Segoe UI",Inter,Roboto,sans-serif}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:var(--ui);font-size:14.5px;line-height:1.55}}
.top{{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:14px;padding:10px 20px;background:var(--bg2);border-bottom:1px solid var(--line)}}
.top h1{{font-size:15px;margin:0;font-weight:600}} .top .sub{{color:var(--muted);font-size:12px}}
.top input{{margin-left:auto;background:var(--bg3);border:1px solid var(--line);color:var(--text);border-radius:6px;padding:6px 10px;font:inherit;width:240px}}
.top button{{background:var(--bg3);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:6px 12px;cursor:pointer;font:inherit}} .top button.pri{{background:var(--acc);color:#04211a;border-color:var(--acc);font-weight:600}}
.wrap{{max-width:1080px;margin:0 auto;padding:20px}}
.how{{background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:18px 22px;margin-bottom:26px}} .how h2{{margin:0 0 8px;font-size:16px}} .how ol{{margin:8px 0 0;padding-left:20px}} .how li{{margin:6px 0}} .how b{{color:var(--acc)}}
.map{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-top:12px}} .map div{{background:var(--bg3);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:13px}} .map b{{display:block;color:var(--acc2);margin-bottom:4px}}
.sec h2{{display:flex;align-items:baseline;gap:12px;font-size:20px;margin:30px 0 4px}} .sec h2 span{{font-family:var(--mono);font-size:12px;color:var(--acc);border:1px solid var(--acc);border-radius:4px;padding:1px 7px}}
.lede{{color:var(--muted);margin:0 0 14px}}
.card{{border:1px solid var(--line);border-radius:8px;background:var(--bg2);margin:10px 0}} .card[open]{{border-color:var(--acc2)}}
.card summary{{display:grid;grid-template-columns:230px 1fr auto;gap:14px;align-items:baseline;padding:12px 16px;cursor:pointer;list-style:none}} .card summary::-webkit-details-marker{{display:none}}
.nm{{font-weight:600}} .one{{color:var(--muted);font-size:13.5px}} .miss{{font-size:11px;color:var(--muted);white-space:nowrap}} .card.missed{{border-left:3px solid var(--err)}}
.body{{padding:4px 16px 16px;border-top:1px solid var(--line)}} .tell{{margin:12px 0}}
.ed{{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--bg)}} .ed .tab{{padding:5px 12px;background:var(--bg3);border-bottom:1px solid var(--line);font-family:var(--mono);font-size:11.5px;color:var(--muted)}}
pre{{margin:0;padding:12px 0;overflow-x:auto;font-family:var(--mono);font-size:12.5px;line-height:1.6}} pre .ln{{display:inline-block;width:40px;text-align:right;padding-right:12px;color:#3d4756;user-select:none}}
.k{{color:#c792ea}} .s{{color:#c3e88d}} .c{{color:#5c6773;font-style:italic}} .n{{color:#f78c6c}} .t{{color:#82aaff}}
.mistake{{margin:12px 0 6px;padding:10px 12px;background:#2a1b1b;border-left:3px solid var(--err);border-radius:0 6px 6px 0}} .mistake b{{color:var(--err)}}
.say{{margin:0;padding:10px 12px;background:#132a24;border-left:3px solid var(--acc);border-radius:0 6px 6px 0}} .say b{{color:var(--acc)}}
.card.hide{{display:none}}
#drill{{display:none;position:fixed;inset:0;background:rgba(6,9,12,.92);z-index:10;overflow:auto;padding:40px 20px}} #drill.on{{display:block}}
.dcard{{max-width:900px;margin:0 auto 18px;background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:18px 22px}} .dcard h3{{margin:0 0 4px;font-size:17px}} .dcard .one{{display:block;margin-bottom:10px}}
.dcard .task{{color:var(--warn);font-weight:600;margin-bottom:10px}} .dcard .ans{{display:none}} .dcard.rev .ans{{display:block}} .dcard button{{background:var(--bg3);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:6px 12px;cursor:pointer;font:inherit;margin-right:8px}} .dcard button.ok{{border-color:var(--acc);color:var(--acc)}} .dcard button.bad{{border-color:var(--err);color:var(--err)}}
.dclose{{max-width:900px;margin:0 auto;text-align:right}} .dclose button{{background:var(--acc);color:#04211a;border:0;border-radius:6px;padding:8px 14px;font-weight:600;cursor:pointer}}
@media (max-width:700px){{.card summary{{grid-template-columns:1fr}}}}
</style></head><body>
<div class="top"><h1>Java primer for LLD rounds</h1><span class="sub">43 cards &middot; SDE-2 to SDE-3 &middot; every idiom compiled</span><input id="q" placeholder="filter cards..."><button id="expand">expand all</button><button id="collapse">collapse</button><button id="drillBtn" class="pri">Drill 3</button></div>
<div class="wrap">
<div class="how"><h2>How to learn this -- so it comes out of your fingers, not your memory</h2>
<ol>
<li><b>Pass 1, once, about 60 minutes.</b> Go A to E in order. At each card, read only the title line and <i>guess what the code looks like</i> before you open it. Open, read the tell, look at the idiom, read the mistake, and say the "Say" line out loud. If your guess was wrong or blank, tick <i>missed</i>. Do not type anything on this pass.</li>
<li><b>Pass 2, daily, 10 minutes, for two weeks.</b> Press <b>Drill 3</b>. It picks three cards, missed ones first, and shows only the task. In a scratch <code>Main.java</code>, type the idiom from memory and run <code>javac</code>. Then reveal and diff. Mark got-it or missed. This is your lost Java touch coming back -- and it is retrieval, so it sticks.</li>
<li><b>Pass 3, inside every LLD.</b> When a workbench step uses a primitive, say its "Say" sentence as you type it. The sentence is the interview answer; the code is the proof.</li>
<li><b>Weekly:</b> drill only missed cards until the list is empty. An empty missed list is the finish line for this page.</li>
</ol>
<div class="map"><div><b>Machine-coding round (90 min)</b>A collections + enums, B locks/CHM/atomics, D strategy/state/factory, E repository split, E testing sentence</div><div><b>Multithreading round (30-45 min)</b>B all of it: condition/wait loop, blocking queue, semaphore, CAS loop, deadlock order, memory model</div><div><b>Design discussion (45 min)</b>C SOLID mapped to your classes, D patterns named when earned, E composition/YAGNI</div><div><b>SDE-3 extras</b>B CompletableFuture, memory model, striping; E idempotency; D chain/facade/proxy in one sentence</div></div>
</div>
{sections}
</div>
<div id="drill"><div class="dclose"><button id="dclose">close</button></div><div id="dcards"></div></div>
<script>
const CARDS={drill};
const KW=/\\b(abstract|boolean|break|case|catch|class|continue|default|do|double|else|enum|extends|final|finally|for|if|implements|import|int|interface|long|new|null|package|private|protected|public|return|static|super|switch|synchronized|this|throw|throws|try|void|while|var|record|true|false)\\b/g,TY=/\\b([A-Z][A-Za-z0-9]*)\\b/g;
function hl(el){{const src=el.textContent;el.innerHTML=src.split('\\n').map((l,i)=>{{let e=l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');const parts=e.split(/(\\/\\/.*$|"(?:[^"\\\\]|\\\\.)*")/);e=parts.map((p,j)=>j%2?(p.startsWith('//')?'<span class="c">'+p+'</span>':'<span class="s">'+p+'</span>'):p.replace(KW,'<span class="k">$1</span>').replace(TY,'<span class="t">$1</span>').replace(/\\b(\\d+(?:\\.\\d+)?)\\b/g,'<span class="n">$1</span>')).join('');return '<span class="ln">'+(i+1)+'</span>'+e;}}).join('\\n');}}
document.querySelectorAll('pre code.java').forEach(hl);
if(location.hash){{const c=document.querySelector(location.hash);if(c){{c.open=true;c.scrollIntoView();}}}}
let missed={{}};try{{missed=JSON.parse(localStorage.getItem('primer.missed')||'{{}}');}}catch(e){{}}
function saveMissed(){{try{{localStorage.setItem('primer.missed',JSON.stringify(missed));}}catch(e){{}}}}
document.querySelectorAll('[data-miss]').forEach(cb=>{{const id=cb.dataset.miss;cb.checked=!!missed[id];cb.closest('.card').classList.toggle('missed',cb.checked);cb.addEventListener('click',e=>e.stopPropagation());cb.addEventListener('change',()=>{{missed[id]=cb.checked;if(!cb.checked)delete missed[id];saveMissed();cb.closest('.card').classList.toggle('missed',cb.checked);}});}});
document.querySelectorAll('.card summary label').forEach(l=>l.addEventListener('click',e=>e.stopPropagation()));
document.getElementById('q').addEventListener('input',e=>{{const q=e.target.value.toLowerCase();document.querySelectorAll('.card').forEach(c=>c.classList.toggle('hide',q&&!c.dataset.name.includes(q)&&!c.textContent.toLowerCase().includes(q)));}});
document.getElementById('expand').onclick=()=>document.querySelectorAll('.card').forEach(c=>c.open=true);
document.getElementById('collapse').onclick=()=>document.querySelectorAll('.card').forEach(c=>c.open=false);
const drill=document.getElementById('drill'),dcards=document.getElementById('dcards');
document.getElementById('dclose').onclick=()=>drill.classList.remove('on');
document.getElementById('drillBtn').onclick=()=>{{
  const miss=CARDS.filter(c=>missed[c.id]),rest=CARDS.filter(c=>!missed[c.id]);
  const shuffle=a=>a.map(x=>[Math.random(),x]).sort((p,q)=>p[0]-q[0]).map(p=>p[1]);
  const pick=shuffle(miss).slice(0,3).concat(shuffle(rest)).slice(0,3);
  dcards.innerHTML=pick.map(c=>{{const code=document.querySelector('#'+c.id+' pre').innerHTML;return '<div class="dcard" data-id="'+c.id+'"><h3>'+c.name+'</h3><span class="one">'+c.one+'</span><div class="task">Type the idiom from memory in a scratch Main.java, then javac it. Only then reveal.</div><div class="ans"><div class="ed"><pre>'+code+'</pre></div></div><p><button class="rev">reveal</button><button class="ok">got it</button><button class="bad">missed</button></p></div>';}}).join('');
  dcards.querySelectorAll('.dcard').forEach(d=>{{const id=d.dataset.id;d.querySelector('.rev').onclick=()=>d.classList.add('rev');d.querySelector('.ok').onclick=()=>{{delete missed[id];saveMissed();sync(id,false);d.style.opacity=.5;}};d.querySelector('.bad').onclick=()=>{{missed[id]=true;saveMissed();sync(id,true);d.style.opacity=.5;}};}});
  drill.classList.add('on');window.scrollTo(0,0);
}};
function sync(id,v){{const cb=document.querySelector('[data-miss="'+id+'"]');if(cb){{cb.checked=v;cb.closest('.card').classList.toggle('missed',v);}}}}
</script></body></html>'''
pathlib.Path("/Users/harishchennupati/answers/lld/java-primer.html").write_text(page)
print("java-primer.html",len(page),"bytes,",len(CARDS),"cards")
