# Builds lld/index.html: every LLD workbench ordered by how often companies that hire from India ask it
# (research/asked-at.json, from research/landscape-*.json), with company chips, review status and Read / Coded ticks.
import pathlib,html,json,re
L=pathlib.Path("/Users/harishchennupati/answers/lld")
T={"parking-lot":"Parking Lot","elevator":"Elevator System","bookmyshow":"Movie Ticket Booking","splitwise":"Splitwise","vending":"Vending Machine","atm":"ATM","rate-limiter":"Rate Limiter","lru":"LRU / LFU Cache","logger":"Logger","tic-tac-toe":"Tic-Tac-Toe","chess":"Chess","snake-ladder":"Snake and Ladder","notification-lld":"Notification Service","file-system":"In-memory File System","stackoverflow":"Stack Overflow","order-book":"Order Book","pubsub":"Pub/Sub System","ride-sharing":"Ride Sharing","food-delivery":"Food Delivery","text-editor":"Text Editor","spreadsheet":"Spreadsheet","digital-wallet":"Digital Wallet","banking":"Banking System","inmem-db":"In-memory Database","cache-eviction":"Cache with Eviction Policies","payment-gateway":"Payment Gateway",
"mt-blocking-queue":"Bounded Blocking Queue","mt-producer-consumer":"Producer-Consumer","mt-rwlock":"Read-Write Lock","mt-ttl-cache":"TTL Cache","mt-striped-map":"Striped Concurrent Map","mt-dining":"Dining Philosophers","mt-h2o":"H2O Barrier","mt-print-series":"Print in Order",
"job-scheduler":"Job Scheduler","meeting-rooms":"Meeting Room Booking and Calendar","inventory-orders":"Inventory, Cart and Orders","train-booking":"Train and Flight Booking","library":"Library Management","leaderboard":"Leaderboard","social-feed":"Social Feed","stock-broker":"Stock Broker","url-shortener-lld":"URL Shortener","task-tracker":"Task Tracker (Jira / Trello)","versioned-kv":"Versioned Key-Value Store","mt-thread-pool":"Thread Pool","snake-game":"Snake Game","car-rental":"Vehicle Rental","autocomplete":"Autocomplete","file-tools":"File Tools (find, du, tail)","circuit-breaker":"Circuit Breaker","rule-engine":"Rules Engine","mt-web-crawler":"Concurrent Web Crawler","amazon-locker":"Amazon Locker","search-engine":"In-memory Search Engine","card-game":"Deck of Cards and Blackjack"}
A=json.loads((L/"research/asked-at.json").read_text())
def reports(s): return A.get(s,{}).get("reports",0)
DONE_NEW={m.group(1) for m in re.finditer(r"^\| ([a-z0-9-]+) \| [AB] \| DONE",(L/"NEW-TRACKER.md").read_text(),re.M)}
def ready(s): return (L/(s+"-workbench.html")).exists() and (s not in NEW or s in DONE_NEW)
def row(s):
    p=L/(s+"-workbench.html"); t=html.escape(T[s]); chips="".join('<i>%s</i>'%html.escape(c) for c in A.get(s,{}).get("companies",[])[:5])
    rev=(L/"research"/(s+"-review.md")).exists() or s=="parking-lot"
    new=s in NEW
    badge='<b class="ok">reviewed</b>' if rev else ('<b class="nw">new</b>' if new and p.exists() else ('<b class="pend">not reviewed</b>' if p.exists() else ''))
    if not ready(s): return '<li class="off"><span>%s</span><span class="ch">%s</span><em>being built</em><span></span></li>'%(t,chips)
    return ('<li><a href="%s-workbench.html">%s</a><span class="ch">%s</span>%s<span class="tk"><label><input type="checkbox" data-k="%s.read">read</label>'
            '<label><input type="checkbox" data-k="%s.coded">coded</label></span></li>')%(s,t,chips,badge,s,s)
NEW={"job-scheduler","meeting-rooms","inventory-orders","train-booking","library","leaderboard","social-feed","stock-broker","url-shortener-lld","task-tracker","versioned-kv","mt-thread-pool","snake-game","car-rental","autocomplete","file-tools","circuit-breaker","rule-engine","mt-web-crawler","amazon-locker","search-engine","card-game"}
sysl=[s for s in T if not s.startswith("mt-")]; mt=[s for s in T if s.startswith("mt-")]
sysl.sort(key=lambda s:(-reports(s),T[s])); mt.sort(key=lambda s:(-reports(s),T[s]))
most=[s for s in sysl if reports(s)>=10]; often=[s for s in sysl if 5<=reports(s)<10]; some=[s for s in sysl if reports(s)<5]
def sec(title,note,lst): return '<h2>%s <small>%s</small></h2><ol>%s</ol>'%(title,note,"".join(row(s) for s in lst))
page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>LLD workbenches</title>
<style>:root{--bg:#0f1419;--bg2:#161b22;--line:#2a3441;--text:#d6dde6;--muted:#7d8896;--acc:#3ddbb0;--warn:#e0b050}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,"Segoe UI",system-ui,sans-serif;font-size:14.5px}
main{max-width:1180px;margin:0 auto;padding:40px 24px 80px} h1{font-size:28px;margin:0 0 6px} p.lead{color:var(--muted);margin:0 0 20px;line-height:1.55}
h2{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:30px 0 8px} h2 small{letter-spacing:0;text-transform:none;font-size:12px;margin-left:8px}
ol{list-style:none;margin:0;padding:0;counter-reset:n} li{counter-increment:n;display:grid;grid-template-columns:2.2em minmax(200px,1.2fr) 2fr 7.5em 9.5em;gap:12px;align-items:center;padding:8px 10px;border-top:1px solid var(--line)}
li::before{content:counter(n,decimal-leading-zero);font-family:"JetBrains Mono",Menlo,monospace;font-size:11px;color:var(--acc)} li a{color:var(--text);text-decoration:none;font-weight:600} li a:hover{color:var(--acc)}
li.off span,li.off em{color:var(--muted)} li em{font-style:normal;font-size:12px}
.ch i{font-style:normal;font-size:11.5px;color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:1px 7px;margin:0 4px 3px 0;display:inline-block}
li b{font-weight:500;font-size:11.5px;border-radius:4px;padding:2px 6px;justify-self:start} b.ok{color:var(--acc);border:1px solid var(--acc)} b.nw{color:#7fb3ff;border:1px solid #7fb3ff} b.pend{color:var(--warn);border:1px solid var(--warn)}
.tk label{font-size:12px;color:var(--muted);margin-right:10px;cursor:pointer} .tk input{accent-color:var(--acc);vertical-align:-2px}
.how{background:var(--bg2);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:0 0 16px;line-height:1.6}
.bar{display:flex;gap:18px;align-items:center;margin:0 0 6px;font-size:13px;color:var(--muted)} .track{flex:1;height:8px;background:var(--bg2);border:1px solid var(--line);border-radius:5px;overflow:hidden} .fill{height:100%;background:var(--acc);width:0}
@media (max-width:800px){li{grid-template-columns:2em 1fr;}.ch,.tk,li b{grid-column:2}}
</style></head><body><main><h1>LLD workbenches</h1>
<p class="lead">Every system in the order companies that hire from India ask it: Indian product companies and startups, FAANG in India, GCCs and US companies in India, and a few UK and Singapore companies. The order comes from about 250 real interview reports from 2023 to 2026 (the folder research/ has them, with links). The chips show who asked it. Each page has five steps: the problem, the twelve-move derivation, the class diagram, the whole code (Java 21, compiled and tested on every build), and the follow-ups with timers.</p>
<div class="how"><b>How to use one.</b> Read 01 and 02 once. Keep 03 open while you read 04. Then close everything and do 05 from a blank file: sixty minutes for the whole system, then the follow-ups one at a time against the timer. Tick <i>read</i> when you have read a page and <i>coded</i> when you have written it from a blank file. Day-one read: <a href="java-primer.html" style="color:var(--acc)">the Java primer</a>.</div>
<div class="bar">read <span id="nr"></span><div class="track"><div class="fill" id="fr"></div></div> coded <span id="nc"></span><div class="track"><div class="fill" id="fc"></div></div></div>
'''+sec("Most asked","asked in 10 or more reports: do these first",most)+sec("Asked often","5 to 9 reports",often)+sec("Asked sometimes","fewer than 5 reports, or one company's favourite",some)+sec("Multithreading","the concurrency round",mt)+'''
</main><script>
const S=(k,v)=>{try{v===undefined?localStorage.removeItem(k):localStorage.setItem(k,v)}catch(e){}}, G=k=>{try{return localStorage.getItem(k)}catch(e){return null}};
const boxes=[...document.querySelectorAll('input[data-k]')];
function tally(){const n=boxes.length/2||1;const r=boxes.filter(b=>b.dataset.k.endsWith('.read')&&b.checked).length,c=boxes.filter(b=>b.dataset.k.endsWith('.coded')&&b.checked).length;
document.getElementById('nr').textContent=r+' / '+n;document.getElementById('nc').textContent=c+' / '+n;document.getElementById('fr').style.width=(100*r/n)+'%';document.getElementById('fc').style.width=(100*c/n)+'%';}
boxes.forEach(b=>{b.checked=G('lldidx.'+b.dataset.k)==='1';b.addEventListener('change',()=>{S('lldidx.'+b.dataset.k,b.checked?'1':undefined);tally();});});tally();
</script></body></html>'''
(L/"index.html").write_text(page)
built=sum(1 for s in T if ready(s))
print("index:",built,"of",len(T),"built;","most",len(most),"often",len(often),"some",len(some),"mt",len(mt))
