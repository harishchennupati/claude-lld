# Parking lot LLD, the one-page version:
# problem (pictures) -> derivation (8 moves, each a picture) -> the class diagram -> the whole code, one file, Javadoc -> follow-ups and practice (question, plain answer, code).
import re,pathlib,html,json,subprocess,tempfile,os
H=pathlib.Path("/Users/harishchennupati/answers/lld")
esc=html.escape
src=(H/"parking-lot/Main.java").read_text(); ext=(H/"parking-lot/Extensions.java").read_text(); tests=(H/"parking-lot/FailureTests.java").read_text()
def sect(a,b=None):
    i=src.index(a); j=src.index(b,i) if b else len(src)
    k=src.rfind("/**",i,j)
    if k>i and src[k:j].rstrip().endswith("*/"): j=k     # a Javadoc block at the very end belongs to the NEXT member: drop it
    return src[i:j].rstrip()+"\n"
def X(a,b):
    marks=[m.start() for m in re.finditer(r"(?m)^// ---- ext:",ext)]+[ext.index("class ExtDemo")]
    i=next(m for m in marks if a in ext[m:m+200]); j=next(m for m in marks if m>i and (b in ext[m:m+200])); return ext[i:j].rstrip()+"\n"
lot_full=sect("interface PaymentProcessor","class WeekendSurgePricing")
ext_avail=lot_full[lot_full.index("    Map<SpotType, Integer> availability()"):lot_full.rindex("/**",0,lot_full.index("    double reportLost("))].rstrip()+"\n"
ext_lost=lot_full[lot_full.index("    double reportLost("):]; ext_lost=ext_lost[:ext_lost.rindex("}")].rstrip()+"\n"
# ---- proper UML class diagram for the whole design
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
B={}; parts=[]
def put(k,x,y,w,name,fields,methods,stereo="",abstract=False):
    g,h=uml(x,y,w,name,fields,methods,stereo,abstract); parts.append(g); B[k]=E(x,y,w,h)
put("gates",10,20,220,"EntryGate / ExitGate",["lot: ParkingLot"],["admit(v): Ticket","checkout(plate, pay): double"])
put("lot",300,20,290,"ParkingLot",["floors: List&lt;ParkingFloor&gt;","active: Map&lt;plate, Ticket&gt;","lock: ReentrantLock","pricing: PricingStrategy","assignment: SpotAssignmentStrategy"],["getInstance()","configure(pricing, assignment)","park(v): Ticket","unpark(plate, pay): double","availability(): Map&lt;SpotType,int&gt;","isFullFor(type): boolean"])
put("floor",300,300,290,"ParkingFloor",["id: String","free: Map&lt;SpotType, Deque&lt;Spot&gt;&gt;","all: Map&lt;id, ParkingSpot&gt;","observers: List&lt;ParkingObserver&gt;"],["addSpot(s)","peekFree(size): ParkingSpot","freeCount(size): int","occupy(s) / vacate(s)","addObserver(o)"])
put("spot",300,560,290,"ParkingSpot",["id: String","type: SpotType","vehicle: Vehicle  (null = free)"],["isFree(): boolean","assign(v) / release()"])
put("fit",300,720,290,"Fit",["ORDER: Map&lt;VehicleType, List&lt;SpotType&gt;&gt;"],[])
put("ticket",640,300,240,"Ticket",["id: int","spot: ParkingSpot","floor: ParkingFloor","vehicle: Vehicle","entryMs / exitMs: long","status: TicketStatus"],[])
put("tstatus",640,470,240,"TicketStatus",["ISSUED, PAID, LOST, CLOSED"],[],"enum")
put("stype",640,560,240,"SpotType",["SMALL, COMPACT, LARGE"],[],"enum")
put("vtype",640,650,240,"VehicleType",["MOTORCYCLE, CAR, TRUCK"],[],"enum")
put("vehicle",10,560,220,"Vehicle",["plate: String","type: VehicleType"],[],"",True)
put("kinds",10,680,220,"Car | Motorcycle | Truck",[],["Car(plate) &rarr; super(plate, CAR)"])
put("obs",10,300,220,"ParkingObserver",[],["onChange(floorId, free)"],"interface")
put("board",10,420,220,"DisplayBoard",[],["onChange(...) &rarr; print"])
put("pricing",930,20,250,"PricingStrategy",[],["price(t: Ticket): double"],"interface")
put("flat",930,110,250,"FlatHourlyPricing",["RATE: Map&lt;SpotType,int&gt;"],["price(t): hours x RATE[size]"])
put("surge",930,215,250,"WeekendSurgePricing",["base: PricingStrategy"],["price(t): base.price(t) x 1.5"])
put("assign",930,330,250,"SpotAssignmentStrategy",[],["find(floor, type): ParkingSpot"],"interface")
put("smallest",930,420,250,"SmallestFitStrategy",[],["find: for size in Fit.ORDER[type]:","  floor.peekFree(size)"])
put("pay",930,530,250,"PaymentProcessor",[],["pay(amount): boolean"],"interface")
put("card",930,620,250,"CardPayment | CashPayment",[],["pay(amount) &rarr; true"])
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
defs='<defs><marker id="uTri" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto"><path d="M0 0L12 6L0 12z" fill="var(--bg3)" stroke="var(--muted)" stroke-width="1.2"/></marker><marker id="uDia" viewBox="0 0 12 12" refX="1" refY="6" markerWidth="12" markerHeight="12" orient="auto"><path d="M1 6L6 1L11 6L6 11z" fill="var(--text)"/></marker><marker id="uArr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10" fill="none" stroke="currentColor" stroke-width="1.3"/></marker></defs>'
edges=[
 ln(B["kinds"]["t"],B["vehicle"]["b"],"inherit"),
 ln(B["board"]["t"],B["obs"]["b"],"inherit"),
 ln(B["flat"]["t"],B["pricing"]["b"],"inherit"),ln((B["surge"]["t"][0]-60,B["surge"]["t"][1]),(B["pricing"]["b"][0]-60,B["pricing"]["b"][1]),"inherit"),
 ln(B["smallest"]["t"],B["assign"]["b"],"inherit"),ln(B["card"]["t"],B["pay"]["b"],"inherit"),
 ln(B["lot"]["b"],B["floor"]["t"],"compose","1..*"),ln(B["floor"]["b"],B["spot"]["t"],"compose","1..*"),
 ln(B["lot"]["r"],B["ticket"]["t"],"compose","active",[(B["ticket"]["t"][0],B["lot"]["r"][1])]),
 ln(B["ticket"]["l"],B["spot"]["r"],"assoc","",[(B["spot"]["r"][0]+20,B["ticket"]["l"][1])]),
 ln(B["ticket"]["b"],B["tstatus"]["t"],"assoc"),
 ln(B["spot"]["r"],B["stype"]["l"],"assoc"),
 ln((B["ticket"]["l"][0],B["ticket"]["l"][1]+30),(B["floor"]["r"][0],B["ticket"]["l"][1]+30),"assoc"),
 ln((B["lot"]["r"][0],B["lot"]["r"][1]-40),(B["pricing"]["l"][0],B["pricing"]["l"][1]),"inject","injected",[(B["pricing"]["l"][0]-30,B["lot"]["r"][1]-40),(B["pricing"]["l"][0]-30,B["pricing"]["l"][1])]),
 ln((B["lot"]["r"][0],B["lot"]["r"][1]-20),(B["assign"]["l"][0],B["assign"]["l"][1]),"inject","",[(B["assign"]["l"][0]-45,B["lot"]["r"][1]-20),(B["assign"]["l"][0]-45,B["assign"]["l"][1])]),
 ln((B["lot"]["r"][0],B["lot"]["r"][1]),(B["pay"]["l"][0],B["pay"]["l"][1]),"inject","",[(B["pay"]["l"][0]-60,B["lot"]["r"][1]),(B["pay"]["l"][0]-60,B["pay"]["l"][1])]),
 ln(B["surge"]["l"],(B["pricing"]["l"][0]-15,B["pricing"]["l"][1]+12),"assoc","",[(B["pricing"]["l"][0]-15,B["surge"]["l"][1])]),
 ln((B["floor"]["l"][0],B["obs"]["r"][1]),B["obs"]["r"],"notify","notifies"),
 ln(B["gates"]["r"],(B["lot"]["l"][0],B["gates"]["r"][1]),"assoc","calls"),
 ln(B["smallest"]["l"],(B["fit"]["r"][0],B["fit"]["r"][1]),"assoc","",[(B["fit"]["r"][0]+30,B["smallest"]["l"][1]),(B["fit"]["r"][0]+30,B["fit"]["r"][1])]),
]
def lg(x,y,kind,text):
    st={"inherit":'stroke="var(--muted)" marker-end="url(#uTri)"',"compose":'stroke="var(--text)" marker-start="url(#uDia)" marker-end="url(#uArr)"',"assoc":'stroke="var(--muted)" marker-end="url(#uArr)"',"inject":'stroke="var(--acc)" stroke-dasharray="5 4" marker-end="url(#uArr)"',"notify":'stroke="var(--acc2)" stroke-dasharray="2 3" marker-end="url(#uArr)"'}[kind]
    return f'<path d="M{x} {y}L{x+44} {y}" fill="none" stroke-width="1.3" {st}/><text x="{x+52}" y="{y+4}" font-size="11" fill="var(--muted)">{text}</text>'
legend='<g>'+lg(20,815,"inherit","extends / implements")+lg(240,815,"compose","owns (composition)")+lg(460,815,"assoc","references")+lg(640,815,"inject","injected (handed in)")+lg(860,815,"notify","notifies")+'<rect x="1040" y="806" width="30" height="18" rx="3" fill="var(--bg3)" stroke="var(--acc)" stroke-dasharray="5 3"/><text x="1078" y="819" font-size="11" fill="var(--muted)">interface</text><text x="1150" y="819" font-size="11" font-style="italic" fill="var(--muted)">abstract</text></g>'
UMLSVG='<svg viewBox="0 0 1230 840" xmlns="http://www.w3.org/2000/svg" style="font-family:var(--mono)">'+defs+"".join(edges)+"".join(parts)+legend+'</svg>'


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
# move 1: sentence with nouns -> boxes
m1=_D+'<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'+_tx(615,47,"a VEHICLE enters a GATE; a FLOOR has SPOTS of three sizes; issue a TICKET; take PAYMENT; answer AVAILABILITY","var(--text)",12.5)
for k,(x,t,sub,acc) in enumerate([(30,"Vehicle","plate, type",1),(230,"Gate","no state: a caller",0),(430,"Floor","its spots",1),(630,"Spot","size, occupant",1),(830,"Ticket","spot, vehicle, times, status",1),(1040,"Availability","a question: a method",0)]):
    w=190 if t=="Ticket" else 170; m1+=_bx(x,110,w,46,t,sub,acc=bool(acc),dash=not acc)+_ar("M%s 64 V110"%(x+w/2))
m1+=_tx(615,190,"solid = has its own state, becomes a class.   dashed = no state of its own: a caller or a method","var(--muted)",11)
# move 2: verbs -> owner of the state
m2=_D
for k,(verb,cls,meth) in enumerate([("assign a vehicle to a spot","Spot  (owns the occupant)","spot.assign(v)"),("find a free spot of a size","Floor  (owns the free lists)","floor.peekFree(size)"),("park a vehicle","ParkingLot  (owns floors + tickets + lock)","lot.park(v)")]):
    y=24+k*56; m2+=_bx(30,y,330,44,verb,"the verb")+_ar("M360 %s H430"%(y+22),True)+_bx(430,y,400,44,cls,"the class whose state it touches",acc=True)+_ar("M830 %s H900"%(y+22),True)+_bx(900,y,300,44,meth,"the method")
m2+=_tx(615,215,"a verb whose state is spread over two classes goes to the class that owns both: that class becomes the orchestrator","var(--muted)",11)
# move 3: rules -> interfaces handed in
m3=_D+_bx(30,60,220,90,"ParkingLot","configure(pricing, assignment)",acc=True)
for k,(t,sub) in enumerate([("PricingStrategy","flat today, surge tomorrow"),("SpotAssignmentStrategy","smallest fit, nearest exit"),("PaymentProcessor","card, cash, UPI")]):
    y=24+k*60; m3+=_ar("M250 105 H330 V%s H400"%(y+22),True,True)+_bx(400,y,300,44,t,sub,dash=True)
    m3+=_bx(760,y,420,44,"%s"%(["FlatHourly / WeekendSurge","SmallestFit / NearestToExit","CardPayment / CashPayment"][k]),"the classes that can be handed in")+_ar("M760 %s H700"%(y+22))
m3+=_tx(615,215,"dashed lavender = handed in. the lot never builds these, so swapping one is a new class and one changed line","var(--muted)",11)
# move 4: two gates, one spot, the gap
m4=_D+_bx(30,30,160,44,"gate 1","reads: C1 free")+_bx(30,110,160,44,"gate 2","reads: C1 free")+_bx(330,70,180,44,"spot C1","free",acc=True)
m4+=_ar("M190 52 H330 V70")+_ar("M190 132 H330 V114")+_tx(260,40,"read","var(--muted)",10.5)+_tx(260,160,"read","var(--muted)",10.5)
m4+='<rect x="540" y="20" width="300" height="140" rx="6" fill="none" stroke="#f38ba8" stroke-dasharray="4 3"/>'+_tx(690,45,"the gap","#f38ba8",12)+_tx(690,70,"both saw free, both write:","#f38ba8",11)+_tx(690,90,"two cars, one spot","#f38ba8",11)+_tx(690,130,"fix: read + write as ONE step, under one lock","var(--text)",11)
m4+=_bx(880,40,320,100,"ParkingLot.lock","find + occupy + issue = one step",acc=True)+_tx(1040,165,"the lock lives where the shared state lives","var(--muted)",10.5)+_tx(1040,185,"listeners (the board) are called after unlock","var(--muted)",10.5)
# move 5: each collection and its question
m5=_D
for k,(q,shape,cost) in enumerate([("next free spot of this size?","Map&lt;SpotType, Deque&lt;Spot&gt;&gt;  head = answer","O(1)"),("this ticket, by plate?","Map&lt;plate, Ticket&gt;","O(1)"),("which floor is this ticket on?","Ticket.floor stored at entry","O(1), no search"),("does a car fit a compact spot?","Fit.ORDER: Map&lt;VehicleType, List&lt;SpotType&gt;&gt;","one lookup")]):
    y=20+k*50; m5+=_bx(30,y,360,40,q,"the question")+_ar("M390 %s H450"%(y+20),True)+_bx(450,y,520,40,shape,"the shape",acc=True)+_ar("M970 %s H1030"%(y+20),True)+_bx(1030,y,170,40,cost,"")
MV={1:_mv(1230,205,m1),2:_mv(1230,230,m2),3:_mv(1230,230,m3),4:_mv(1230,200,m4),5:_mv(1230,225,m5)}


# ---------- three more move pictures
RED="#ff6b6b"; GRN="#3ddbb0"
# move 6: the ticket is a state machine, and the order at exit
m6=_D
for k,(t,sub,acc) in enumerate([("ISSUED","at entry",0),("PAID","money moved",1),("CLOSED","spot freed",1)]):
    m6+=_bx(30+k*230,30,190,44,t,sub,acc=bool(acc))
    if k<2: m6+=_ar("M%s 52 H%s"%(220+k*230,260+k*230),True)
m6+=_bx(30,110,190,44,"LOST","reported lost: bill the cap")+_ar("M125 74 V110")+_ar("M220 132 H720 V74",True)
m6+='<rect x="760" y="20" width="450" height="150" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'+_tx(985,44,"the order at exit, and why it is this order","var(--text)",12)
for k,l in enumerate(["1 peek the ticket (do not remove it)","2 compute the fee, TAKE PAYMENT","3 only now: PAID, remove, release, vacate, CLOSED","a declined card leaves the driver parked and able to retry;","a second checkout finds no ticket and is refused"]):
    m6+=_tx(775,66+k*20,l,"var(--muted)" if k>2 else "var(--text)",11,"start")
m6+=_tx(615,195,"a status enum plus one rule: nothing is committed before the money moved. Lost ticket = the same order with the cap as the fee.","var(--muted)",11)
# move 7: one lock, and how it scales
m7=_D+'<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'+_tx(300,42,"one lock: is it a bottleneck? do the arithmetic","var(--text)",12)
for k,l in enumerate(["locked part of park: a lookup, a deque poll, two pointer writes: ~0.5 us","ten gates, a car every 3 s each: 3 parks a second, 1.5 us of lock a second","contention: 1.5 us in 1,000,000 us, once in ~700,000 seconds","the barrier arm serialises cars far more than the lock does","the slow thing inside the lock: the card payment, ~500 ms. The weak spot."]):
    m7+=_tx(35,66+k*24,l,RED if k==4 else "var(--muted)",11,"start")
m7+=_tx(880,42,"the upgrade ladder, in the order you would climb it","var(--text)",12)
for k,(t,sub) in enumerate([("1 payment outside the lock","PAYING state on the ticket; commit in a second short section"),("2 a lock per floor","gates on different floors never wait for each other"),("3 compare-and-set per spot","claim occupant null -> vehicle in one hardware step; losers try the next")]):
    m7+=_bx(600,58+k*50,600,42,t,sub,acc=(k==0))
# move 8: what can go wrong, and the test for each
m8=_D
for k,(t,sub,fix) in enumerate([("payment fails at exit","spot leaked, driver stuck","pay before commit; test: decline, then retry with cash"),("the display board throws","spot lost from the deque","publish after unlock, catch; test: a throwing observer"),("two gates, one spot","double booking","one lock; test: 50 threads, one latch, one winner"),("60 min + 1 ms","billed one hour","round any started hour up; test: injected clock")]):
    y=24+k*46; m8+=_bx(30,y,290,40,t,sub)+_ar("M320 %s H380"%(y+20),True)+_bx(380,y,820,40,fix,"",acc=True)
m8+=_tx(615,215,"every claim the design makes has a failure test: FailureTests.java runs seven of them and must print ALL PASS","var(--muted)",11)
MV[6]=_mv(1230,210,m6); MV[7]=_mv(1230,220,m7); MV[8]=_mv(1230,230,m8)

# ---------- problem picture
pp=_D+_bx(30,40,170,50,"vehicle at a gate","car, bike, truck")+_ar("M200 65 H250",True)+_bx(250,40,232,50,"find the smallest free spot","fits: small < compact < large",acc=True)+_ar("M482 65 H520",True)+_bx(520,40,160,50,"issue a ticket","spot, floor, time")+_ar("M680 65 H740",True)+_bx(740,40,180,50,"board updates","free counts per floor")
pp+=_bx(30,120,170,50,"ticket at exit","hours parked")+_ar("M200 145 H260",True)+_bx(260,120,200,50,"fee: hourly by size","rounded up; changeable",acc=True)+_ar("M460 145 H520",True)+_bx(520,120,160,50,"take payment","card or cash")+_ar("M680 145 H740",True)+_bx(740,120,180,50,"free the spot","board updates")
pp+=_bx(960,40,240,50,"query: full for a truck?","how many compact free?")+_bx(960,120,240,50,"reject when full","")
pp+=_tx(615,205,"three flows: park, unpark, query. Many gates at the same time: two vehicles must never get the same spot.","var(--muted)",11.5)
PROBLEM=_mv(1230,220,pp)

# ---------- derivation moves text (from the old step 02, kept, plus 6-8)
MOVES=[
("Move 1: underline the nouns. Every noun with its own state becomes a class.","Reading the paragraph again: a <b>vehicle</b> enters a <b>gate</b>; a <b>floor</b> has <b>spots</b> of three sizes; I issue a <b>ticket</b>; I take <b>payment</b>; I answer <b>availability</b>. Vehicle has a plate and a type: a class. Spot has a size and whoever is in it: a class. Floor owns spots: a class. Ticket has a spot, a vehicle, two times and a status: a class. The lot holds all of it: a class. Gate has nothing of its own to remember, so it is a thin caller, not a model. Availability is a question I answer, so it is a method, not a class.",1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.","\"assign a vehicle to a spot\" changes the spot's occupant, so <code>spot.assign(v)</code>. \"find a free spot of a size\" reads the floor's free lists, so <code>floor.peekFree(size)</code>. \"park\" touches floors, tickets and the lock at once; only the lot sees all three, so <code>lot.park(v)</code>. When a verb's state is spread over two classes, it goes to the class that owns both. That is how small models and one orchestrator appear without planning them.",2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.","Pricing will change (flat today, surge on weekends). Which spot to pick will change (smallest fit today, nearest exit tomorrow). How to pay will change (card, cash, UPI). Each becomes a one-method interface the lot is <i>given</i> in <code>configure()</code>, never builds itself. A rule nobody will change stays a plain method. This is where the patterns come from, not the other way round: a swappable rule behind an interface is <b>Strategy</b>; a new rule that wraps an old one (surge over flat) is <b>Decorator</b>; a floor that announces 'counts changed' to whoever subscribed, without knowing what a screen is, is <b>Observer</b>. I do them; I do not announce them.",3),
("Move 4: state that many callers change at the same time gets one owner and one lock.","Ten gates all change spot occupancy and the ticket map. Between \"I saw C1 free\" and \"I took C1\" another gate can take it; that gap is where two cars get one spot. So find, occupy and issue must be one step under one lock, in the class that owns both maps: the lot. And anything that only listens (the display board) is called after the lock is released, never inside it.",4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).","\"next free spot of this size\": a deque per size, the head is the answer. \"this ticket, by plate\": a map. \"which floor is this ticket on\": store the floor on the ticket at entry so exit never searches. \"does a car fit a compact spot\": a small table, vehicle type to sizes, smallest first. Every scan avoided here is a question not fumbled in the concurrency round, because the scan would have been inside the lock.",5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.","A ticket is ISSUED at entry, PAID when the money moved, CLOSED when the spot is freed, LOST if reported lost. Writing the states down forces the question the interviewer will ask: what if payment fails? The answer is an order: peek the ticket, price it, take the payment, and only then commit (PAID, remove, release, vacate, CLOSED). A declined card leaves everything as it was and the driver retries; a second checkout finds no ticket and is refused. Lost ticket is the same order with the daily cap as the fee.",6),
("Move 7: one lock is not a bottleneck here; say why with numbers, then name the ladder.","The locked part of a park is a lookup and two pointer writes, under a microsecond. Ten gates admitting a car every few seconds each is a few parks a second: the lock is busy a millionth of the time, and the physical barrier serialises far more than the lock does. The one slow thing inside the lock is the card payment, so the honest first upgrade is to take payment outside the lock with a PAYING state and commit in a second short section; then a lock per floor; then compare-and-set per spot. Say the arithmetic first, the ladder second.",7),
("Move 8: list what can go wrong, and write the test for each before the interview is over.","Payment fails at exit (the spot must not leak). The display board throws (the deque must not lose a spot). Two gates, one spot (exactly one winner). Sixty minutes and one millisecond (two hours, not one). Time comes from an injected clock so the tests can say 'Saturday 10:00'. Each of these is a few lines in FailureTests.java; a design that cannot show its tests is a claim.",8),
]

# ---------- follow-ups and practice: question, plain answer about what the code does, code
FU=[
("Add weekend surge pricing, 1.5x, without touching ParkingLot.","functional",10,
 "Pricing is already an interface, so surge is one new class that wraps the flat rule: it asks the flat rule for the price, looks at the ticket's exit day, and multiplies by 1.5 on Saturday and Sunday. The lot does not change; the only edit is the line where the pricing is handed in. The exit day comes from the ticket's exit time, which the lot's injected clock stamped, so a test can make any day a Saturday.",
 sect("class WeekendSurgePricing","class EntryGate")),
("Two cars, two gates, one compact spot left. Prove it cannot double-book, with a test.","non-functional",10,
 "The race lives between reading 'C1 is free' and writing 'C1 is taken'. park() does find, occupy and assign inside one lock, so no other gate can run in that gap. The proof: fifty gates wait on one latch, the latch opens, all fifty call park for the last compact spot, and the test counts the tickets that came back: exactly one, forty-nine get 'Lot full'.",
 sect("        // the race: fifty gates","        System.out.println(\"lost ticket fee")),
("Ten gates on one lock. Does that scale, or are you serialising the whole car park?","non-functional",5,
 "Yes it scales, and the answer is arithmetic. The locked part of park is a map lookup, a deque poll and two pointer writes: about half a microsecond. Ten gates each admitting a car every three seconds is three parks a second, so the lock is held for a millionth of each second; the barrier arm serialises cars far more than the lock does. The one slow thing inside the lock is payment at exit, about half a second on a card gateway, and that is the honest weak spot: the first upgrade takes the payment outside the lock with a PAYING state on the ticket and commits in a second short section. After that, a lock per floor so floors never wait for each other, and after that compare-and-set on each spot: claim the occupant from null to the vehicle in one hardware step, and a loser tries the next spot.",
 X("lock per floor","lock-free spot")+"\n"+X("lock-free spot","a truck needs two adjacent")),
("A driver lost the ticket. Implement it.","functional",10,
 "The duration is unknown, so the fee is a flat daily cap. reportLost does the same thing as unpark in the same order: find the ticket without removing it, take the cap as payment, and only then mark it LOST, remove it, release the spot, put the spot back in the free deque and mark CLOSED. If the payment fails nothing has changed. The TicketState table in the second block is the explicit version of the rule: every transition that is not in the table throws, so a double exit or a close before pay is refused rather than silently done.",
 ext_lost+"\n"+X("ticket lifecycle","lock per floor")),
("Payment fails at the exit gate. What is the state of the system, and show me the code handling it.","functional",10,
 "Nothing is half done. unpark peeks the ticket (does not remove it), prices it, and asks the payment processor. If that returns false it throws and returns; the ticket is still ISSUED, the spot is still held, the driver tries another card or pays cash. Only after a successful payment does it mark PAID, remove the ticket from the active map, release the spot, give it back to the floor's deque, and mark CLOSED. A second checkout finds no active ticket and is refused. Billing rounds any started hour up, so sixty minutes and one millisecond is two hours. The second block is the same order written against the transition table.",
 sect("    double unpark(String plate","    Map<SpotType, Integer> availability()")+"\n"+X("exit-time failure","class ExtDemo")),
("The app asks 'how many compact spots are free on F2?' a thousand times a second. Make it O(1).","non-functional",5,
 "No new structure. The floor already keeps a deque of free spots per size, so the answer is the size of F2's compact deque: one call, O(1). Lot-wide availability sums that per floor and size, never a scan of spots. The reads take the lot's lock so a count is never torn by a concurrent park; that costs nanoseconds. If they push to a million spots, keep a lot-level count map updated under the same lock.",
 "// on the floor: one deque per size, so the count is its size\nint freeCount(SpotType st) { return free.get(st).size(); }   // O(1)\n\n// F2, compact, a thousand times a second:\nint n = f2.freeCount(SpotType.COMPACT);\n\n"+ext_avail),
("Now a truck needs two adjacent large spots.","twist",10,
 "Spots gain a neighbour link (a map from a spot id to the spot beside it). Assignment looks for two free large neighbours; a spot with no neighbour simply has no run. The ticket holds a list of spots instead of one. The reservation is the whole point: TruckParking finds the run and assigns both spots inside the same locked section, so a second truck can never take half of the pair; either both are taken or nothing was touched. Say the word atomic. The lock-free design makes this hard, which is a reason to prefer the lock here.",
 X("a truck needs two adjacent","persistence seam")),
("Nearest spot to the exit instead of smallest fit.","twist",5,
 "A second assignment strategy: it is given a distance per spot from configuration, looks at the head of each fitting size's deque, and returns the closest of those heads. The lot is untouched; one line in configure() changes. A full version keeps each size's free spots in a heap ordered by distance instead of a deque, which makes the head the nearest at O(log n) per change.",
 X("a second assignment","ticket lifecycle")),
("Persist it. Or: now there are many branches.","twist",5,
 "The two maps in the lot become a repository behind an interface (find a ticket by plate, save, remove), and the in-memory version is one implementation. The services do not change. The spot claim, which is now a deque poll under a lock, becomes a conditional database update: set the spot's vehicle where it is null; zero rows updated means someone else got it. That is the database's compare-and-set, and it is the same idea as the lock: one atomic step decides the winner.",
 X("persistence seam","exit-time failure")+"\n// the spot claim in SQL: the database's compare-and-set\n// UPDATE spot SET vehicle = ? WHERE id = ? AND vehicle IS NULL;   -- 1 row updated = you got it; 0 = someone else did\n"),
("Where does time come from, and how do you test the weekend rule on a Tuesday?","design",5,
 "The lot has a Clock it was handed; it stamps entry and exit times on the ticket, and pricing reads the ticket, never the wall clock. A test hands in a clock that says 'Saturday 10:00', parks, moves the clock forward, unparks, and checks the fee is 20 times 1.5. The failure tests below do exactly that, and also decline a payment and retry, throw from an observer, and race fifty threads.",
 tests[tests.index("        // 5. billing"):tests.index("        // 7. occupy")]),
("Which pattern is where, and why did each one earn its place?","design",5,
 "None of them was chosen up front; each is what a move in the derivation produced. Strategy is move 3: pricing, assignment and payment are rules that will change, so each sits behind a one-method interface the lot is handed. Decorator is surge: a new rule that wraps the old one instead of replacing it. Observer is move 4's rule that the board must not be inside the lock: the floor announces 'counts changed' to whoever subscribed. The state table is move 6: a ticket's life written down so illegal moves throw. Singleton is only the lot's getInstance() at the edge; services are handed the lot, so tests build a fresh one. Factory did not earn its place yet: it pays when vehicles are built from configuration strings.",
 "// Strategy: a rule behind an interface, handed in\ninterface PricingStrategy { double price(Ticket t); }\nvoid configure(PricingStrategy p, SpotAssignmentStrategy a) { pricing = p; assignment = a; }\n\n// Decorator: wrap the old rule, add to it\nclass WeekendSurgePricing implements PricingStrategy { private final PricingStrategy base; /* ... base.price(t) * 1.5 on weekends */ }\n\n// Observer: the floor announces; it does not know what a screen is\ninterface ParkingObserver { void onChange(String floorId, Map<SpotType, Integer> free); }\nvoid publish(Map<SpotType, Integer> counts) { for (ParkingObserver o : observers) o.onChange(id, counts); }   // after the lock\n\n// State: the ticket's life as a table; an illegal move throws\nenum TicketState { ISSUED, PAID, LOST, CLOSED; /* ALLOWED = {ISSUED->PAID|LOST, PAID->CLOSED, LOST->CLOSED} */ }\n"),
("Which SOLID letter is where in this code?","design",5,
 "S: each class has one reason to change. The spot tracks its occupant, the floor its free lists, the lot the orchestration and the lock, a pricing class the money; nobody does two of these. O: weekend surge was a new class and one changed line, the lot did not open. L: any PricingStrategy drops in and the lot never checks which one it got. I: the interfaces have one method each; a payment class is never asked to price. D: the lot depends on the interfaces it is handed in configure(), not on FlatHourlyPricing; tests hand in fakes and a fixed clock.",
 "// S: one reason to change each\nclass ParkingSpot { /* occupant only */ }   class ParkingFloor { /* free lists only */ }   class ParkingLot { /* orchestration + lock */ }\n// O: new behaviour = new class, one changed line, nothing opened\nlot.configure(new WeekendSurgePricing(new FlatHourlyPricing(), ZoneId.of(\"Asia/Kolkata\")), new SmallestFitStrategy());\n// L: any implementation drops in; the lot never checks the concrete type\ndouble fee = pricing.price(t);\n// I: one method per interface\ninterface PaymentProcessor { boolean pay(double amount); }\n// D: depend on the interface, hand in the implementation; tests hand in fakes\nlot.setClock(() -> fixedSaturdayMs);   lot.unpark(\"AAA\", amount -> false);   // a declining card\n"),
("Enum sizes or Spot subclasses? Where would you use a Factory?","design",3,
 "Enum, until a size gains behaviour of its own. Three sizes that differ only in what fits and what they cost are data: a row in the fit table and a rate. An EV spot with a charger that must be started and stopped is behaviour, and that is when a subclass pays. Factory earns its place when spots or vehicles are built from configuration strings: a registry that maps 'EV' to a constructor turns adding a type into one registration instead of a growing switch.",
 "// data, not classes: a size is a row\nstatic final Map<VehicleType, List<SpotType>> ORDER = Map.of(VehicleType.CAR, List.of(SpotType.COMPACT, SpotType.LARGE), /* ... */);\nstatic final Map<SpotType, Integer> RATE = Map.of(SpotType.SMALL, 10, SpotType.COMPACT, 20, SpotType.LARGE, 40);\n\n// when a size gains behaviour, a subclass pays\nclass EvSpot extends ParkingSpot { void startCharging() { /* talks to the charger */ } void stopCharging() { /* ... */ } }\n\n// a factory only once creation logic grows: a registry, so a new type is one registration\nMap<String, Function<String, ParkingSpot>> registry = Map.of(\"EV\", id -> new EvSpot(id, SpotType.COMPACT));\nParkingSpot s = registry.get(kind).apply(id);\n"),
]

# ---------- page
CSS='''
:root{--bg:#0f1419;--bg2:#161b22;--bg3:#1c2330;--line:#2a3441;--text:#d6dde6;--muted:#7d8896;--acc:#3ddbb0;--acc2:#7cc4ff;--warn:#f0a35e;--err:#ff6b6b;--mono:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;--ui:-apple-system,"Segoe UI",Inter,Roboto,sans-serif}
html,body{background:var(--bg);color:var(--text);margin:0} body{font-family:var(--ui);font-size:14.5px;line-height:1.65}
main{max-width:1060px;margin:0 auto;padding:34px 26px 80px}
h1{font-size:28px;margin:0 0 4px} .lead{color:var(--muted);margin:0 0 18px;max-width:80ch}
h2{font-size:19px;margin:40px 0 12px;color:var(--acc)} h2 .num{color:var(--acc);opacity:.8;margin-right:10px;font-size:14px;font-family:var(--mono)} h2{scroll-margin-top:12px}
h3{font-size:15px;margin:26px 0 8px;color:var(--text)}
p{max-width:84ch} code{font-family:var(--mono);font-size:12.5px;color:var(--acc2)}
.toc{margin:10px 0 26px;padding:14px 18px 10px;background:var(--bg2);border:1px solid var(--line);border-radius:10px}
.toc .t{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
.toc ol{list-style:none;margin:0;padding:0} .toc li{border-top:1px solid var(--line)} .toc li:first-child{border-top:0}
.toc a{display:flex;gap:12px;align-items:baseline;padding:6px;color:var(--text);text-decoration:none;font-size:13.5px} .toc a:hover{color:var(--acc)}
.toc a .n{color:var(--acc);font-family:var(--mono);font-size:11.5px;min-width:1.8em;text-align:right} .toc a .s{color:var(--muted);font-size:12px;margin-left:auto}
.fullboard{margin:10px 0 14px;padding:10px;background:var(--bg2);border:1px solid var(--line);border-radius:8px} .fullboard svg{width:100%;height:auto;display:block}
.fullboard.mv{padding:6px}
.req{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:12px 0} .req>div{background:var(--bg2);border:1px solid var(--line);border-radius:8px;padding:10px 14px} .req b{color:var(--acc)} .req ul{margin:6px 0 0;padding-left:18px} .req li{font-size:13.5px}
.grade{background:var(--bg2);border-left:3px solid var(--acc);padding:12px 16px;border-radius:0 8px 8px 0;margin:14px 0} .grade b{color:var(--acc)}
.move{margin:22px 0} .move h3{margin:0 0 6px} .move p{color:var(--text)}
.ed{background:var(--bg2);border:1px solid var(--line);border-radius:8px;overflow:hidden;margin:10px 0}
.ed .tab{font-family:var(--mono);font-size:11.5px;color:var(--muted);padding:8px 14px;border-bottom:1px solid var(--line)}
pre{margin:0;padding:14px 0;overflow-x:auto;font-family:var(--mono);font-size:12.5px;line-height:1.6;tab-size:4} pre .ln{display:inline-block;width:44px;text-align:right;padding-right:14px;color:#3d4756;user-select:none}
.k{color:#c792ea} .s{color:#c3e88d} .c{color:#5c6773;font-style:italic} .n{color:#f78c6c} .t{color:#82aaff} .d{color:#7fa66f;font-style:italic}
.card{background:var(--bg2);border:1px solid var(--line);border-radius:10px;margin:14px 0;overflow:hidden} .card .ch{display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid var(--line)} .card .ch h3{margin:0;font-size:14.5px} .card .cb{padding:12px 16px}
.kind{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--acc2);border:1px solid var(--acc2);border-radius:999px;padding:2px 8px}
.timer{margin-left:auto;font-family:var(--mono);font-size:12px;background:transparent;color:var(--acc);border:1px solid var(--acc);border-radius:999px;padding:4px 12px;cursor:pointer} .timer.run{background:var(--acc);color:#04211a}
details{margin:8px 0 0} summary{cursor:pointer;color:var(--acc2);font-size:13.5px} details .ans{margin:10px 0 6px;max-width:none;line-height:1.7}
.miss textarea{width:100%;min-height:90px;background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:10px;font-family:var(--mono);font-size:12.5px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0} th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top} th{color:var(--muted);font-weight:500}
'''
def ed(code,tab="Main.java"): return '<div class="ed"><div class="tab">'+tab+'</div><pre><code class="java">'+esc(code)+'</code></pre></div>'
secs=[]
def h2(t,sub=""): secs.append((t,sub)); return '<h2 id="s%d"><span class="num">%02d</span>%s</h2>'%(len(secs)-1,len(secs),t)
body='<h1>Parking Lot</h1><p class="lead">LLD in Java. Scope: one lot, in memory, one process. Read the derivation, keep the class diagram beside you, then read the code top to bottom; the follow-ups at the end each carry their code. Reference compiled on OpenJDK 21; the demo, seven failure tests and a fifty-thread race pass.</p>%%TOC%%'
body+=h2("The problem, and what it must do","three flows, two lists")+PROBLEM
body+='''<div class="req"><div><b>Functional requirements</b><ul><li>Park: find the smallest free spot that fits, mark it taken, issue a ticket.</li><li>Unpark: take the ticket, compute the fee from time parked, take payment, free the spot.</li><li>Three vehicle kinds (motorcycle, car, truck), three spot sizes (small, compact, large); a bigger spot may hold a smaller vehicle.</li><li>Pricing: hourly by spot size, rounded up, and changeable without touching the rest.</li><li>Payment at exit by cash or card.</li><li>Answer "is it full for a truck?" and "how many compact spots are free?"</li><li>Reject when full.</li></ul></div>
<div><b>Non-functional requirements</b><ul><li>Many gates at the same time: two vehicles must never get the same spot.</li><li>Finding a spot must not scan every spot: one step per size, O(1).</li><li>Pricing and assignment rules swappable without changing the core.</li><li>One source of truth for which spots are taken: the floor's per-size free deque.</li><li>Nothing half-done: a failed payment leaves the driver parked and able to retry.</li><li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
<div class="grade"><b>Say before typing:</b> in memory, one process, one lot; one vehicle takes one spot; billing rounds up to the hour; the first floor with a fitting spot wins, then the smallest size on that floor. Out of scope for now, named: lost tickets, passes, EV, reservations. <b>A worked example to replay in your head:</b> 10:00 a car arrives, floor 1 has one small, one compact, one large free: the car gets the compact, ticket #1. 10:01 a truck: the large. 10:02 another car: compact and large gone, a car cannot use small, rejected. 12:30 car #1 leaves: 2.5 h rounds to 3, compact is 20 an hour, fee 60, spot free, board updates.</div>'''
body+=h2("From the requirements to the design: eight moves","every class, pattern, lock and test comes from one of these")
body+='<p class="lead">Run these on any LLD (elevator, BookMyShow, Splitwise) and the class diagram, the patterns, the lock and the tests fall out; nothing is chosen up front.</p>'
for i,(t,txt,k) in enumerate(MOVES,1): body+='<div class="move"><h3>%s</h3>%s<p>%s</p></div>'%(t,MV[k],txt)
body+=h2("The whole design","one class diagram; keep it beside the code")+'<div class="fullboard">'+UMLSVG+'</div>'
body+='''<p><b>How to read a box.</b> Top: the class name (<i>italic</i> = abstract, never <code>new</code>-ed; dashed border = interface; &laquo;enum&raquo; = a fixed list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = extends or implements. Filled diamond = owns: the lot owns floors, a floor owns spots, the lot owns the active tickets. Plain arrow = references: a ticket points at its spot, floor and vehicle. Dashed lavender = handed in through <code>configure()</code>. Dotted blue = notifies. <b>Where state lives:</b> the floor has the free deques and the observers; the lot has the floors, the active tickets, the handed-in rules and the one lock; a spot has its occupant; a ticket has its spot, floor, vehicle, times and status.</p>'''
body+=h2("The whole code, one file","Main.java as you would type it; Javadoc on every class and method")+'<p class="lead">Read it with the diagram beside you. The comment above each class or method says what it does; read only those first for the shape, then the bodies for the mechanics.</p>'+ed(src)
body+=h2("Follow-ups and practice","the questions they ask; each with a plain answer of what the code does, then the code")
body+='''<div class="grade"><b>How to use this section.</b> First implement the whole system from a blank <code>Main.java</code>, sixty minutes, until a main compiles and runs. Then take the questions one at a time: read it, start its timer, answer <i>in code</i> in your own file, and only then open the fold. The fold says in plain English what the reference code does, then shows it. The miss log at the bottom is the output of the session.</div>'''
body+='<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3><button class="timer" data-min="60">start 60:00</button></div><div class="cb">"Design a parking lot. Multiple floors, different vehicle sizes. Cars enter through entry gates and leave through exit gates; a ticket on the way in, payment on the way out. I want working code, not a diagram. Go." Before typing, write your five to eight clarifying questions; then type in the order of the code above: enums, vehicle, spot and the fit table, ticket, the two interfaces with one implementation each, the floor, the lot with its lock and the exit order, the gates, a main with the race.</div></div>'
for i,(q,kind,mins,ans,code) in enumerate(FU,1):
    body+='<div class="card"><div class="ch"><span class="kind">%s</span><h3>%d &middot; %s</h3><button class="timer" data-min="%d">start %d:00</button></div><div class="cb"><details><summary>Answer, after the timer</summary><p class="ans">%s</p>%s</details></div></div>'%(kind,i,esc(q),mins,mins,ans,ed(code,"reference"))
body+='<div class="card"><div class="ch"><h3>Miss log</h3></div><div class="cb"><div class="miss"><p>Three specific lines: what the reference did that you did not. Saved in this browser.</p><textarea id="miss" placeholder="1.&#10;2.&#10;3."></textarea></div></div></div>'
body+=h2("The failure tests","seven claims the design makes, each proven")+'<p class="lead">Every claim in the derivation has a test here. Run: <code>javac Main.java FailureTests.java &amp;&amp; java FailureTests</code>, which prints ALL PASS.</p>'+ed(tests,"FailureTests.java")
SHORT=[("The problem","three flows, two lists"),("The derivation","eight moves"),("The whole design","the class diagram"),("The whole code","one file, Javadoc"),("Follow-ups and practice","question, plain answer, code"),("The failure tests","seven claims proven")]
toc='<nav class="toc"><p class="t">Contents</p><ol>'+"".join('<li><a href="#s%d"><span class="n">%02d</span><span>%s</span><span class="s">%s</span></a></li>'%(i,i+1,a,b) for i,(a,b) in enumerate(SHORT))+'</ol></nav>'
body=body.replace("%%TOC%%",toc)
JS=r'''
const KW=/\b(abstract|boolean|break|case|catch|class|continue|default|do|double|else|enum|extends|final|finally|for|if|implements|import|int|interface|long|new|null|package|private|protected|public|return|static|super|switch|synchronized|this|throw|throws|try|void|volatile|while|true|false|var|record)\b/g;
const TY=/\b([A-Z][A-Za-z0-9]*)\b/g;
function hl(src){let inDoc=false;return src.split('\n').map((l,i)=>{let e=l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');const t=e.trim();let out;
 if(inDoc||t.startsWith('/**')){out='<span class="d">'+e+'</span>';if(t.startsWith('/**'))inDoc=!t.endsWith('*/');else if(t.endsWith('*/'))inDoc=false;}
 else{const parts=e.split(/(\/\/.*$|"(?:[^"\\]|\\.)*")/);out=parts.map((p,j)=>j%2?(p.startsWith('//')?'<span class="c">'+p+'</span>':'<span class="s">'+p+'</span>'):p.replace(KW,'<span class="k">$1</span>').replace(TY,'<span class="t">$1</span>').replace(/\b(\d+(?:\.\d+)?)\b/g,'<span class="n">$1</span>')).join('');}
 return '<span class="ln">'+(i+1)+'</span>'+out;}).join('\n');}
document.querySelectorAll('pre code.java').forEach(el=>{el.innerHTML=hl(el.textContent);});
document.querySelectorAll('button.timer[data-min]').forEach(b=>{const total=+b.dataset.min*60;let left=total,id=null;const show=()=>{b.textContent=(id?'':'start ')+Math.floor(left/60)+':'+String(left%60).padStart(2,'0');};b.onclick=()=>{if(id){clearInterval(id);id=null;left=total;b.classList.remove('run');show();return;}b.classList.add('run');id=setInterval(()=>{left--;show();if(left<=0){clearInterval(id);id=null;b.classList.remove('run');b.textContent='time';}},1000);show();};});
const miss=document.getElementById('miss');try{miss.value=localStorage.getItem('pl.miss')||'';}catch(e){}miss.addEventListener('input',()=>{try{localStorage.setItem('pl.miss',miss.value);}catch(e){}});
'''
page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Parking Lot, LLD</title><style>'+CSS+'</style></head><body><main>'+body+'</main><script>'+JS+'</script></body></html>'
out=H/"parking-lot.html"; out.write_text(page); print("written",out,len(page))
# guard: the whole file compiles and the tests pass
d=tempfile.mkdtemp(prefix="pl_"); open(os.path.join(d,"Main.java"),"w").write(src); open(os.path.join(d,"FailureTests.java"),"w").write(tests); open(os.path.join(d,"Extensions.java"),"w").write(ext)
r=subprocess.run(["/opt/homebrew/opt/openjdk@21/bin/javac","Main.java","FailureTests.java","Extensions.java"],cwd=d,capture_output=True,text=True)
if r.returncode!=0: raise SystemExit("CODE DOES NOT COMPILE:\n"+r.stderr)
r=subprocess.run(["/opt/homebrew/opt/openjdk@21/bin/java","FailureTests"],cwd=d,capture_output=True,text=True)
if "ALL PASS" not in r.stdout: raise SystemExit("TESTS FAIL:\n"+r.stdout[-800:])
print("guard: compiles; failure tests ALL PASS")
