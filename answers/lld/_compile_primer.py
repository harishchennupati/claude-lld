import subprocess,pathlib,sys,re
sys.path.insert(0,"/Users/harishchennupati/answers/lld")
from _primer_data import CARDS
D=pathlib.Path("/Users/harishchennupati/answers/lld/primer/_compile"); D.mkdir(parents=True,exist_ok=True)
for f in D.glob("*"): f.unlink()
J="/opt/homebrew/opt/openjdk/bin/javac"
bad=0
for c in CARDS:
    cls="Snip_"+c["id"]
    code=re.sub(r'(?m)^(final |abstract )?class ', lambda m: "static "+(m.group(1) or "")+"class ", c["code"])   # nested -> static, as top-level would be
    src="import java.util.*;\nimport java.util.concurrent.*;\nimport java.util.concurrent.atomic.*;\nimport java.util.concurrent.locks.*;\n\nclass "+cls+" {\n"+code+"\n}\n"
    (D/f"{cls}.java").write_text(src)
    r=subprocess.run([J,"-Xlint:none","-d",str(D),str(D/f"{cls}.java")],capture_output=True,text=True)
    if r.returncode!=0:
        bad+=1; print("FAIL",c["id"]); print(r.stderr[:1200])
print(f"{len(CARDS)} cards, {bad} failed")
