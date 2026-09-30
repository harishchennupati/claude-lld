#!/usr/bin/env python3
# usage: python3 _verify.py <slug> [shots]   -> re-runs the spec (guard), checks page JS syntax + 5 steps + copy buttons, optional screenshots of steps 1,2,5
import sys,subprocess,re,json,pathlib,os
slug=sys.argv[1]; shots="shots" in sys.argv
L=pathlib.Path("/Users/harishchennupati/answers/lld"); D=pathlib.Path("/Users/harishchennupati/.claude/jobs/fbe2926d/tmp")/("v_"+slug); D.mkdir(parents=True,exist_ok=True)
r=subprocess.run(["python3",str(L/"specs"/(slug+".py"))],capture_output=True,text=True,cwd=str(L))
ok_guard="ALL PASS" in r.stdout
print("guard:","OK" if ok_guard else "FAIL "+(r.stdout[-300:]+r.stderr[-500:]))
page=L/(slug+"-workbench.html"); t=page.read_text()
m=re.findall(r"<script>([\s\S]*?)</script>",t); js=m[-1]
open(D/"js.txt","w").write(js)
r=subprocess.run(["node","-e","const fs=require('fs');try{new Function(fs.readFileSync(process.argv[1],'utf8'));console.log('ok')}catch(e){console.log('SYNTAX '+e.message)}",str(D/"js.txt")],capture_output=True,text=True)
print("js:",r.stdout.strip())
S=json.loads(re.search(r"const STEPS=(\[.*?\]);\nconst RAW",t,re.S).group(1))
print("steps:",len(S),[s["stage"] for s in S])
print("copy buttons:",sum(s["body"].count('class="copy"') for s in S),"| cards:",S[4]["body"].count('class="card"'),"| moves:",S[1]["body"].count('<div class="move"><h3>'))
bad=[s["title"] for s in S if len(s["body"])<1500]; print("thin steps:",bad or "none")
frag=len(re.findall(r"<li>(?:and|which|therefore|so|but|or) ",t)); print("fragment bullets:",frag)
if shots:
    CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    for n in (1,2,5):
        h=t.replace("let cur=parseInt(localStorage.getItem('%s.step')||'1',10);"%slug,"let cur=%d;"%n)
        (D/("s%d.html"%n)).write_text(h)
        png=D/("s%d.png"%n)
        if png.exists(): png.unlink()
        pr=subprocess.Popen([CH,"--headless=new","--disable-gpu","--hide-scrollbars","--no-first-run","--window-size=1700,%d"%(2600 if n!=2 else 6000),"--virtual-time-budget=5000","--user-data-dir="+str(D/"chrome-profile"),"--screenshot="+str(png),"file://"+str(D/("s%d.html"%n))],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        import time
        for _ in range(90):   # chrome sometimes writes the png and then never exits: poll, then kill
            if pr.poll() is not None: break
            if png.exists() and png.stat().st_size>0: time.sleep(1); break
            time.sleep(1)
        if pr.poll() is None: pr.kill()
        if not png.exists(): print("screenshot %d missing (chrome did not render); retry"%n)
    print("shots in",D)
