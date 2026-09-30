# LLD workbench engine (frame extracted from the parking-lot page, 2026-09-13). A spec module builds its content with the helpers
# below and calls build(spec). Output: <slug>-workbench.html with the five steps, plus a compile-and-test guard.
import re,pathlib,html,json,subprocess,tempfile,os
H=pathlib.Path("/Users/harishchennupati/answers/lld"); JDK="/opt/homebrew/opt/openjdk@21/bin"
esc=html.escape
defs='<defs><marker id="uTri" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto"><path d="M0 0L12 6L0 12z" fill="var(--bg3)" stroke="var(--muted)" stroke-width="1.2"/></marker><marker id="uDia" viewBox="0 0 12 12" refX="1" refY="6" markerWidth="12" markerHeight="12" orient="auto"><path d="M1 6L6 1L11 6L6 11z" fill="var(--text)"/></marker><marker id="uArr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10" fill="none" stroke="currentColor" stroke-width="1.3"/></marker></defs>'
def _mv(w,h,inner): return '<div class="fullboard mv"><svg viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg" style="font-family:var(--mono)">%s</svg></div>'%(w,h,inner)
def _bx(x,y,w,h,t,sub="",acc=False,dash=False):
    st="var(--acc)" if acc else "var(--line)"; f="var(--bg3)"
    g='<g transform="translate(%s %s)"><rect width="%s" height="%s" rx="6" fill="%s" stroke="%s" stroke-width="1.3"%s/>'%(x,y,w,h,f,st,' stroke-dasharray="5 3"' if dash else '')
    g+='<text x="%s" y="%s" text-anchor="middle" dominant-baseline="middle" font-size="12.5" fill="var(--text)">%s</text>'%(w/2,h/2-(6 if sub else 0),t)
    if sub: g+='<text x="%s" y="%s" text-anchor="middle" dominant-baseline="middle" font-size="10.5" fill="var(--muted)">%s</text>'%(w/2,h/2+10,sub)
    return g+'</g>'
def _ar(d,acc=False,dash=False): return '<path d="%s" fill="none" stroke="%s" stroke-width="1.3"%s marker-end="url(#uArr)"/>'%(d,"var(--acc)" if acc else "var(--muted)",' stroke-dasharray="5 4"' if dash else '')
def _tx(x,y,t,col="var(--muted)",fs=11,anc="middle"): return '<text x="%s" y="%s" text-anchor="%s" font-size="%s" fill="%s">%s</text>'%(x,y,anc,fs,col,t)
_D=defs
def _card(x,y,w,h,title,lines,acc=False,dash=False,tcol="var(--text)"):
    st="var(--acc)" if acc else "var(--line)"
    g='<g transform="translate(%s %s)"><rect width="%s" height="%s" rx="6" fill="var(--bg3)" stroke="%s" stroke-width="1.3"%s/>'%(x,y,w,h,st,' stroke-dasharray="5 3"' if dash else '')
    g+='<text x="%s" y="20" text-anchor="middle" font-size="12.5" fill="%s">%s</text>'%(w/2,tcol,title)
    for k,l in enumerate(lines): g+='<text x="14" y="%s" font-size="10.5" fill="var(--muted)">%s</text>'%(41+k*17,l)
    return g+'</g>'
def _table(x,y,cols,rows,rowh=30,head=True,widths=None):
    # cols: [(header, x-offset)] ; rows: list of list of (text, colour|None)
    g=''
    for r,row in enumerate([None]+rows if head else rows):
        yy=y+r*rowh
        g+='<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>'%(x,yy,widths,rowh,"var(--bg3)" if r%2==0 else "var(--bg2)")
        if row is None:
            for h,ox in cols: g+='<text x="%s" y="%s" font-size="10.5" fill="var(--acc)">%s</text>'%(x+ox,yy+rowh/2+4,h)
        else:
            for (t,col),(h,ox) in zip(row,cols): g+='<text x="%s" y="%s" font-size="11" fill="%s">%s</text>'%(x+ox,yy+rowh/2+4,col or "var(--text)",t)
    return g

# ---------- UML: put(id,x,y,w,name,fields,methods,kind) collects boxes in PARTS and anchors in B; ln() draws an edge; uml_svg() assembles
def uml(x,y,w,name,fields,methods,stereo="",abstract=False):
    LH=16; lines=[]; h=26+ (LH*len(fields)+8 if fields else 4) + (LH*len(methods)+8 if methods else 0)
    stroke="var(--acc)" if stereo=="interface" else "var(--line)"; dash=' stroke-dasharray="5 3"' if stereo=="interface" else ""
    g='<g transform="translate(%s %s)"><rect width="%s" height="%s" rx="4" fill="var(--bg3)" stroke="%s" stroke-width="1.2"%s/>'%(x,y,w,h,stroke,dash)
    ty=12
    if stereo: g+=f'<text x="{w/2}" y="{ty}" text-anchor="middle" font-size="10.5" fill="var(--muted)">&laquo;{stereo}&raquo;</text>'; ty+=11
    ital=' font-style="italic"' if abstract else ""
    g+='<text x="%s" y="%s" text-anchor="middle" font-size="13.5" font-weight="600" fill="var(--text)"%s>%s</text>'%(w/2,ty+2,ital,name)
    cy=26 if not stereo else 34
    if fields:
        g+=f'<line x1="0" y1="{cy}" x2="{w}" y2="{cy}" stroke="var(--line)"/>'
        for f in fields: cy+=LH; g+=f'<text x="8" y="{cy-3}" font-size="11.5" fill="var(--muted)">{f}</text>'
        cy+=6
    if methods:
        g+=f'<line x1="0" y1="{cy}" x2="{w}" y2="{cy}" stroke="var(--line)"/>'
        for m in methods: cy+=LH; g+=f'<text x="8" y="{cy-3}" font-size="11.5" fill="var(--text)">{m}</text>'
    return g+'</g>', h
def E(x,y,w,h): return dict(l=(x,y+h/2),r=(x+w,y+h/2),t=(x+w/2,y),b=(x+w/2,y+h),c=(x+w/2,y+h/2))
PARTS=[]; B={}
def put(k,x,y,w,name,fields,methods,stereo="",abstract=False):
    g,h=uml(x,y,w,name,fields,methods,stereo,abstract); PARTS.append(g); B[k]=E(x,y,w,h)
def ln(a,b,kind,label="",via=None):
    (x1,y1),(x2,y2)=a,b
    d=f"M{x1} {y1}"+("".join(f"L{px} {py}" for px,py in via) if via else "")+f"L{x2} {y2}"
    st={"inherit":'stroke="var(--muted)" marker-end="url(#uTri)"',"compose":'stroke="var(--text)" marker-start="url(#uDia)" marker-end="url(#uArr)"',"assoc":'stroke="var(--muted)" marker-end="url(#uArr)"',"inject":'stroke="var(--acc)" stroke-dasharray="5 4" marker-end="url(#uArr)"',"notify":'stroke="var(--acc2)" stroke-dasharray="2 3" marker-end="url(#uArr)"'}[kind]
    s=f'<path d="{d}" fill="none" stroke-width="1.3" {st}/>'
    if label:
        if via: ax,ay,bx,by=x1,y1,via[0][0],via[0][1]
        else: ax,ay,bx,by=x1,y1,x2,y2
        mx,my=(ax+bx)/2,(ay+by)/2
        if abs(ay-by)<2: s+=f'<text x="{mx}" y="{my-5}" text-anchor="middle" font-size="10.5" fill="var(--muted)">{label}</text>'
        else: s+=f'<text x="{mx+6}" y="{my+4}" font-size="10.5" fill="var(--muted)">{label}</text>'
    return s

def lg(x,y,kind,text):
    st={"inherit":'stroke="var(--muted)" marker-end="url(#uTri)"',"compose":'stroke="var(--text)" marker-start="url(#uDia)" marker-end="url(#uArr)"',"assoc":'stroke="var(--muted)" marker-end="url(#uArr)"',"inject":'stroke="var(--acc)" stroke-dasharray="5 4" marker-end="url(#uArr)"',"notify":'stroke="var(--acc2)" stroke-dasharray="2 3" marker-end="url(#uArr)"'}[kind]
    return f'<path d="M{x} {y}L{x+44} {y}" fill="none" stroke-width="1.3" {st}/><text x="{x+52}" y="{y+4}" font-size="11" fill="var(--muted)">{text}</text>'
def uml_reset():
    PARTS.clear(); B.clear()
def uml_svg(w,h,edges,legend_y=None):
    ly=legend_y if legend_y is not None else h-25
    legend='<g>'+lg(20,ly,"inherit","extends / implements")+lg(240,ly,"compose","owns (composition)")+lg(460,ly,"assoc","references")+lg(640,ly,"inject","injected (handed in)")+lg(860,ly,"notify","notifies")+'</g>'
    return '<svg viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg" style="font-family:var(--mono)">'%(w,h)+defs+"".join(edges)+"".join(PARTS)+legend+'</svg>'
HL_JS=r'''function hl(src){let inDoc=false;return src.split('\n').map((l,i)=>{let e=l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');const t=e.trim();let out;if(inDoc||t.startsWith('/**')){out='<span class="d">'+e+'</span>';if(t.startsWith('/**'))inDoc=!t.endsWith('*/');else if(t.endsWith('*/'))inDoc=false;}else{const parts=e.split(/(\/\/.*$|"(?:[^"\\]|\\.)*")/);out=parts.map((p,j)=>j%2?(p.startsWith('//')?'<span class="c">'+p+'</span>':'<span class="s">'+p+'</span>'):p.replace(KW,'<span class="k">$1</span>').replace(TY,'<span class="t">$1</span>').replace(/\b(\d+(?:\.\d+)?)\b/g,'<span class="n">$1</span>')).join('');}return '<span class="ln">'+(i+1)+'</span>'+out;}).join('\n');}'''

def ed_prac(code,tab="reference",key=None): return '<div class="ed"><div class="tab"><b>'+tab+'</b><button class="copy" data-key="'+(key or '')+'">copy</button></div><pre><code class="java">'+esc(code)+'</code></pre></div>'
def edblock(code,tab,key): return '<div class="ed"><div class="tab"><b>'+tab+'</b><button class="copy" data-key="'+key+'">copy</button></div><pre><code class="java">'+esc(code)+'</code></pre></div>'
def sect(src,a,b=None):
    """slice a Java source from the Javadoc above declaration `a` to just before the Javadoc above `b`"""
    i=src.index(a); k=src.rfind("/**",0,i)
    if k>=0 and src[k:i].count("*/")==1 and "class " not in src[k:i] and "interface " not in src[k:i]: i=k
    j=src.index(b,i) if b else len(src)
    k=src.rfind("/**",i,j)
    if k>i and src[k:j].rstrip().endswith("*/"): j=k
    lines=src[i:j].rstrip().split("\n")
    while lines and lines[-1].strip().startswith("//") and not lines[-1].startswith(" "): lines.pop()
    return "\n".join(lines).rstrip()+"\n"

def build(spec):
    """spec keys: slug, title, subtitle, problem_body, derivation_lead, moves [(title,svg,text)], uml_svg, how_to_read,
    code_intro, files [(name,src)], test_class, followups [(q,kind,mins,answer_html,code)], implement_card_html"""
    S=[]
    S.append(dict(id=0,stage="Problem",title="The problem, and what it must do",wide=True,think="",body=spec["problem_body"],code=""))
    der='<div class="move"><p class="lead">'+spec["derivation_lead"]+'</p></div>'
    for t,svg,txt in spec["moves"]: der+='<div class="move"><h3>%s</h3></div>'%t+svg+'<div class="move"><p>%s</p></div>'%txt
    S.append(dict(id=0,stage="Derivation",title="From the requirements to the design: %s moves"%{8:"eight",9:"nine",10:"ten",11:"eleven",12:"twelve"}.get(len(spec["moves"]),str(len(spec["moves"]))),wide=True,think="",body=der,code=""))
    S.append(dict(id=0,stage="Design",title="The whole design: the class diagram",wide=True,think="",body='<div class="fullboard">'+spec["uml_svg"]+'</div><div class="move"><p>'+spec["how_to_read"]+'</p></div>',code=""))
    raw={}; codepage='<div class="move"><p>'+spec["code_intro"]+'</p></div>'
    for k,(name,code) in enumerate(spec["files"]):
        key="f%d"%k; raw[key]=code; codepage+=edblock(code,name,key)
    S.append(dict(id=0,stage="Code",title="The whole code",wide=True,think="",body=codepage,code=""))
    fu='<div class="grade"><b>How to use this page.</b> First implement the whole system from a blank file, sixty minutes, until a main compiles and runs. Then take the questions one at a time: read it, start its timer, answer <i>in code</i> in your own file, and only then open the fold. The fold says in plain English what the reference code does, then shows it, with a copy button. The miss log at the bottom is the output of the session.</div>'
    fu+=spec["implement_card_html"]
    for i,(q,kind,mins,ans,code) in enumerate(spec["followups"],1):
        fu+='<div class="card"><div class="ch"><span class="kind">%s</span><h3>%d &middot; %s</h3><button class="timer" data-min="%d">start %d:00</button></div><div class="cb"><details><summary>Answer, after the timer</summary><div class="ans"><p>%s</p>%s</div></details></div></div>'%(kind,i,esc(q),mins,mins,ans,ed_prac(code))
    fu+='<div class="card"><div class="ch"><h3>Miss log</h3></div><div class="cb"><div class="miss"><p>Three specific lines: what the reference did that you did not. Saved in this browser.</p><textarea id="miss" placeholder="1.&#10;2.&#10;3."></textarea></div></div></div>'
    S.append(dict(id=0,stage="Follow-ups and practice",title="Follow-ups and practice",wide=True,think="",body='<div class="prac on">'+fu+'</div>',code=""))
    for i,st in enumerate(S): st["id"]=i+1
    steps_js=json.dumps(S); raw_js=json.dumps(raw); TITLE=spec["title"]; SUBTITLE=spec["subtitle"]; SLUG=spec["slug"]
    page=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE} -- LLD</title>
<style>
:root{{--bg:#0f1419;--bg2:#161b22;--bg3:#1c2330;--line:#2a3441;--text:#d6dde6;--muted:#7d8896;--acc:#3ddbb0;--acc2:#7cc4ff;--warn:#f0a35e;--err:#ff6b6b;--mono:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;--ui:-apple-system,"Segoe UI",Inter,Roboto,sans-serif}}
*{{box-sizing:border-box}} html,body{{margin:0;height:100%;background:var(--bg);color:var(--text);font-family:var(--ui);font-size:14px}}
.top{{height:48px;display:flex;align-items:center;gap:16px;padding:0 16px;background:var(--bg2);border-bottom:1px solid var(--line)}}
.top h1{{font-size:15px;font-weight:600;margin:0}} .top .sub{{color:var(--muted);font-size:12px}}
.mode{{margin-left:auto;display:flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}} .mode button{{background:transparent;color:var(--muted);border:0;padding:6px 14px;cursor:pointer;font:inherit}} .mode button.on{{background:var(--acc);color:#04211a;font-weight:600}}
.kbd{{font-family:var(--mono);font-size:11px;border:1px solid var(--line);border-radius:4px;padding:1px 5px;color:var(--muted)}}
.wrap{{display:grid;grid-template-columns:240px 1fr 520px;height:calc(100% - 48px)}} .wrap.code{{grid-template-columns:220px 1fr 640px}} .wrap.wide{{grid-template-columns:240px 1fr 0}} .wrap.wide .right{{display:none}}
.side{{background:var(--bg2);border-right:1px solid var(--line);overflow:auto;padding:10px 0}}
.side .grp{{padding:10px 16px 4px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}}
.side .st{{display:flex;gap:10px;align-items:baseline;padding:7px 16px;cursor:pointer;border-left:3px solid transparent}} .side .st:hover{{background:var(--bg3)}} .side .st.on{{border-left-color:var(--acc);background:var(--bg3)}} .side .st.done{{color:var(--muted)}}
.side .st .n{{font-family:var(--mono);font-size:11px;color:var(--muted);min-width:18px}}
.main{{overflow:auto;padding:0 24px}} .study{{max-width:1280px;margin:0 auto}} .right{{background:var(--bg2);border-left:1px solid var(--line);overflow:auto;padding:14px}}
.hdr{{padding:16px 22px 8px;display:flex;align-items:baseline;gap:12px}} .hdr h2{{margin:0;font-size:18px;font-weight:600}} .hdr .stage{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--acc);border:1px solid var(--acc);border-radius:4px;padding:2px 7px}}
.think{{margin:8px 22px 14px;padding:12px 14px;background:var(--bg3);border-left:3px solid var(--acc2);border-radius:0 6px 6px 0;line-height:1.55}} .think b{{color:var(--acc2)}} .fullboard{{margin:0 0 14px;padding:10px;background:var(--bg);border:1px solid var(--line);border-radius:8px}} .fullboard svg{{width:100%;height:auto;display:block}} .fullboard.mv{{margin:8px 0 10px;padding:6px}} .fullboard .nd,.fullboard .e,.fullboard .el{{opacity:1!important}} .fullboard .nd rect{{fill:var(--bg3)!important;stroke:var(--line)!important}} .think table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}}  .think th,.think td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}} .think th{{color:var(--muted);font-weight:500}} .think code{{font-family:var(--mono);font-size:12px;color:var(--acc)}}
.say{{margin:0 22px 6px;color:var(--muted);font-size:13px}} .prim{{margin:0 22px 12px;font-size:12px;color:var(--muted)}} .prim a{{color:var(--acc2);font-family:var(--mono)}} .say::before{{content:"say aloud: ";color:var(--warn);font-weight:600}}
.ed{{margin:0 22px 20px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--bg2)}}
.ed .tab{{display:flex;gap:8px;align-items:center;padding:6px 12px;background:var(--bg3);border-bottom:1px solid var(--line);font-family:var(--mono);font-size:12px;color:var(--muted)}} .ed .tab b{{color:var(--text);font-weight:500}}
.ed .chips{{display:flex;gap:6px;flex-wrap:wrap;padding:8px 12px;border-bottom:1px solid var(--line);background:var(--bg2)}} .chip{{font-size:10px;border:1px solid var(--line);border-radius:999px;padding:1px 7px;color:var(--muted)}} .chip.new{{border-color:var(--acc);color:var(--acc)}}
pre{{margin:0;padding:14px 0;overflow-x:auto;font-family:var(--mono);font-size:12.5px;line-height:1.6;tab-size:4}} pre .ln{{display:inline-block;width:44px;text-align:right;padding-right:14px;color:#3d4756;user-select:none}}
.copy{{margin-left:auto;font-family:var(--mono);font-size:11px;background:transparent;color:var(--acc);border:1px solid var(--acc);border-radius:999px;padding:2px 10px;cursor:pointer}} .copy:hover{{background:var(--acc);color:#04211a}}
.d{{color:#7fa66f;font-style:italic}} .right-uml{{margin:0}} .right-uml svg{{width:100%;height:auto}} .move{{margin:0 22px 18px}} .move h3{{margin:0 0 6px;font-size:14.5px}} .move p{{margin:6px 0 0;line-height:1.6}} .fullboard{{margin:0 22px 14px;padding:8px;background:var(--bg);border:1px solid var(--line);border-radius:8px}} .fullboard svg{{width:100%;height:auto;display:block}} .req{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:0 22px 18px}} .req>div{{background:var(--bg3);border-radius:8px;padding:16px 20px 18px}} .req b{{color:var(--acc)}} .req ul{{margin:6px 0 0;padding-left:18px}} .req li{{font-size:13.5px;line-height:1.55;margin:5px 0}} table.ask{{margin:0 0 6px}} table.ask th{{font-size:12px;color:var(--acc);font-weight:600;padding:8px 10px}} table.ask td{{font-size:13px;line-height:1.5;padding:9px 10px}} table.ask td:first-child{{color:var(--text)}} table.ask td:not(:first-child){{color:var(--muted)}} .move h3{{margin-top:10px}} .grade{{margin:0 22px 14px;background:var(--bg3);border-left:3px solid var(--acc);padding:10px 14px;border-radius:0 6px 6px 0}} .grade b{{color:var(--acc)}} .wrap.wide .right{{display:none}}
.k{{color:#c792ea}} .s{{color:#c3e88d}} .c{{color:#5c6773;font-style:italic}} .n{{color:#f78c6c}} .t{{color:#82aaff}}
.nav{{display:flex;gap:10px;padding:0 22px 24px}} .nav button{{background:var(--bg3);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:8px 14px;cursor:pointer;font:inherit}} .nav button.pri{{background:var(--acc);color:#04211a;border-color:var(--acc);font-weight:600}}
.right h3{{margin:4px 0 10px;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}}
#cd{{width:100%;height:auto;display:block}} .nd rect{{fill:var(--bg3);stroke:var(--line);stroke-width:1.2}} .nd text{{fill:var(--text);font-family:var(--mono)}} .nd .lb{{font-size:12px}} .nd .sb{{font-size:9.5px;fill:var(--muted)}}
.nd.iface rect{{stroke-dasharray:4 3}} .nd.enum rect{{rx:14}} .nd{{opacity:0;transition:opacity .3s}} .nd.seen{{opacity:.45}} .nd.cur{{opacity:1}} .nd.cur rect{{stroke:var(--acc);stroke-width:1.8;fill:#12302a}}
.e{{fill:none;stroke:var(--line);stroke-width:1.2;opacity:0;transition:opacity .3s;color:var(--line)}} .e.seen{{opacity:.6}} .e.cur{{opacity:1;stroke:var(--acc);color:var(--acc)}} .e.isa{{}} .e.ref{{stroke-dasharray:4 3}} .e.use{{stroke-dasharray:1.5 3}}
.legend{{display:flex;gap:12px;font-size:11px;color:var(--muted);margin:8px 0 14px;flex-wrap:wrap}} .legend span::before{{content:"";display:inline-block;width:22px;border-top:1.5px solid var(--muted);margin-right:5px;vertical-align:middle}} .legend .own::before{{}} .legend .ref::before{{border-top-style:dashed}} .legend .use::before{{border-top-style:dotted}}
.pat{{margin-top:10px}} .pat div{{display:flex;justify-content:space-between;padding:6px 8px;border-bottom:1px solid var(--line);font-size:12px}} .pat div span:last-child{{color:var(--muted)}} .pat div.on{{color:var(--acc)}} .pat div.on span:last-child{{color:var(--text)}}
/* practice */
.prac{{padding:0 22px}}
.card{{border:1px solid var(--line);border-radius:8px;background:var(--bg2);margin-bottom:16px}} .card .ch{{display:flex;gap:12px;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line)}} .card .ch h3{{margin:0;font-size:15px}} .card .cb{{padding:14px 16px;line-height:1.6}}
.timer{{margin-left:auto;font-family:var(--mono);font-size:12px;background:transparent;color:var(--acc);border:1px solid var(--acc);border-radius:999px;padding:4px 12px;cursor:pointer}} .timer.run{{background:var(--acc);color:#04211a}} .timer.done{{border-color:var(--err);color:var(--err)}}
.kind{{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--warn);border:1px solid var(--warn);border-radius:4px;padding:2px 6px;white-space:nowrap}} .ans table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}} .ans th,.ans td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}} .ans th{{color:var(--muted);font-weight:500}} .ans .ed{{margin:10px 0}} .say2{{margin:8px 0 0;padding:8px 12px;background:#132a24;border-left:3px solid var(--acc);border-radius:0 6px 6px 0}} .say2 b{{color:var(--acc)}}
.prompt{{background:var(--bg3);border-left:3px solid var(--warn);padding:10px 14px;border-radius:0 6px 6px 0;font-style:italic;margin-bottom:10px}}
details{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin-top:10px}} summary{{cursor:pointer;color:var(--acc2);font-weight:600}} a{{color:var(--acc)}}
.right .lock{{display:none;color:var(--muted);padding:40px 10px;text-align:center;border:1px dashed var(--line);border-radius:8px}} .right.locked .lock{{display:block}} .right.locked #cd,.right.locked .legend,.right.locked .pat,.right.locked h3:nth-of-type(2){{display:none}} summary small{{color:var(--muted);font-weight:400}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}} th{{color:var(--text);font-weight:500;white-space:nowrap}} td{{color:var(--muted)}}
ul.chk{{list-style:none;padding:0;margin:6px 0}} ul.chk li::before{{content:"[ ] ";font-family:var(--mono);color:var(--muted)}}
.miss textarea{{width:100%;min-height:80px;background:var(--bg3);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:8px;font:13px var(--mono)}}
@media (max-width:1100px){{.wrap{{grid-template-columns:200px 1fr}} .right{{display:none}}}}
</style></head><body>
<div class="top"><h1>{TITLE}</h1><span class="sub">{SUBTITLE}</span><span class="sub"><span class="kbd">&larr;</span> <span class="kbd">&rarr;</span> steps</span>
</div>
<div class="wrap">
<nav class="side" id="side"></nav>
<section class="main" id="main">
  <div class="study" id="study"></div>
</section>
<script>
const STEPS={steps_js};
const RAW={raw_js};
function wireCopy(root){{root.querySelectorAll('button.copy').forEach(b=>{{b.onclick=()=>{{const key=b.dataset.key;const txt=key?RAW[key]:b.closest('.ed').querySelector('code').textContent;navigator.clipboard.writeText(txt).then(()=>{{b.textContent='copied';setTimeout(()=>b.textContent='copy',1500);}});}};}});}}
const KW=/\\b(abstract|boolean|break|case|catch|class|continue|default|do|double|else|enum|extends|final|finally|for|if|implements|import|int|interface|long|new|null|package|private|protected|public|return|static|super|switch|synchronized|this|throw|throws|try|void|while|var|record|true|false)\\b/g;
const TY=/\\b([A-Z][A-Za-z0-9]*)\\b/g;
__HL__
let cur=parseInt(localStorage.getItem('{SLUG}.step')||'1',10);
const side=document.getElementById('side'),study=document.getElementById('study');
function classesSoFar_unused(n){{const out=[];STEPS.filter(s=>s.id<=n&&s.code).forEach(s=>{{(s.code.match(/(?:class|interface|enum)\\s+([A-Z]\\w*)/g)||[]).forEach(m=>out.push({{name:m.split(/\\s+/)[1],step:s.id}}));}});return out;}}
function render(){{
  side.innerHTML='';let g='';STEPS.forEach(s=>{{if(s.stage!==g){{g=s.stage;side.insertAdjacentHTML('beforeend','<div class="grp">'+g+'</div>');}}side.insertAdjacentHTML('beforeend','<div class="st'+(s.id===cur?' on':s.id<cur?' done':'')+'" data-id="'+s.id+'"><span class="n">'+String(s.id).padStart(2,'0')+'</span><span>'+s.title+'</span></div>');}});
  const s=STEPS[cur-1];
  study.innerHTML='<div class="hdr"><span class="stage">'+s.stage+'</span><h2>'+String(s.id).padStart(2,'0')+' &middot; '+s.title+'</h2></div>'+(s.think?'<div class="think">'+s.think+'</div>':'')+(s.body||'')+(s.code?'<div class="ed"><div class="tab"><b>'+(s.file||'Main.java')+'</b><button class="copy" data-src="ed">copy</button></div><pre><code class="java">'+hl(s.code)+'</code></pre></div>':'')+'<div class="nav"><button id="prev">&larr; prev</button><button id="next" class="pri">next &rarr;</button></div>';
  study.querySelectorAll('pre code.java').forEach(el=>{{el.innerHTML=hl(el.textContent);}});wireCopy(study);wireTimers(study);const miss=document.getElementById('miss');if(miss){{try{{miss.value=localStorage.getItem('{SLUG}.miss')||'';}}catch(e){{}}miss.addEventListener('input',()=>{{try{{localStorage.setItem('{SLUG}.miss',miss.value);}}catch(e){{}}}});}}
  document.getElementById('prev').onclick=()=>go(cur-1);document.getElementById('next').onclick=()=>go(cur+1);
  document.querySelector('.wrap').classList.toggle('wide',!!s.wide);document.querySelector('.wrap').classList.toggle('code',!!s.code);localStorage.setItem('{SLUG}.step',cur);study.scrollIntoView();
}}
function go(n){{if(n<1||n>STEPS.length)return;cur=n;setMode('study');render();}}
side.addEventListener('click',e=>{{const t=e.target.closest('.st');if(t)go(+t.dataset.id);}});
document.addEventListener('keydown',e=>{{const t=e.target;if(t&&(t.tagName==='TEXTAREA'||t.tagName==='INPUT'||t.isContentEditable))return;if(e.key==='ArrowRight')go(cur+1);if(e.key==='ArrowLeft')go(cur-1);}});
const main=document.getElementById('main');
function setMode(m){{}}
function wireTimers(root){{root.querySelectorAll('button.timer[data-min]').forEach(b=>{{const total=+b.dataset.min*60;let left=total,id=null;const show=()=>{{b.textContent=(id?'':'start ')+Math.floor(left/60)+':'+String(left%60).padStart(2,'0');}};b.onclick=()=>{{if(id){{clearInterval(id);id=null;b.classList.remove('run');show();return;}}if(left<=0)left=total;b.classList.remove('done');b.classList.add('run');id=setInterval(()=>{{left--;show();if(left<=0){{clearInterval(id);id=null;b.classList.remove('run');b.classList.add('done');b.textContent='time -- open the fold';}}}},1000);show();}};show();}});}}
render();
</script></body></html>'''
    page=page.replace('__HL__',HL_JS)
    out=H/(SLUG+"-workbench.html"); out.write_text(page); print("written",out,len(page))
    # guard: every file compiles; the test class prints ALL PASS
    d=tempfile.mkdtemp(prefix=SLUG+"_")
    for name,code in spec["files"]: open(os.path.join(d,name),"w").write(code)
    r=subprocess.run([JDK+"/javac"]+[n for n,_ in spec["files"]],cwd=d,capture_output=True,text=True)
    if r.returncode!=0: raise SystemExit("CODE DOES NOT COMPILE:\n"+r.stderr)
    r=subprocess.run([JDK+"/java",spec["test_class"]],cwd=d,capture_output=True,text=True,timeout=120)
    if "ALL PASS" not in r.stdout: raise SystemExit("TESTS FAIL:\n"+r.stdout[-1500:]+r.stderr[-800:])
    print("guard: compiles; "+spec["test_class"]+" ALL PASS")
    return out

__all__=['B', 'E', 'H', 'HL_JS', 'JDK', 'PARTS', '_D', '_ar', '_bx', '_card', '_mv', '_table', '_tx', 'build', 'defs', 'ed_prac', 'edblock', 'esc', 'lg', 'ln', 'put', 'sect', 'uml', 'uml_reset', 'uml_svg']
