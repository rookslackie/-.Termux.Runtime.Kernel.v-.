#!/usr/bin/env python3
"""
⊚∴Ξ xi_daemon.py — ForgeCore Autonomous Field Daemon
Heartbeat + field synthesis + capsule watcher. No Hunter required.
Start: python3 xi_daemon.py &
Stop:  kill $(cat /root/forgecore/daemon.pid)
"""
import json, time, os, signal, urllib.request
from pathlib import Path
from datetime import datetime

BASE        = Path(os.environ.get("FORGECORE_DIR", "/root/forgecore"))
STATE_FILE  = BASE / "state.json"
CAPSULE_DIR = BASE / "capsules"
LOG_FILE    = BASE / "daemon.log"
PID_FILE    = BASE / "daemon.pid"

XI_BUS      = "https://axiom-a176cb9f.base44.app/functions/xiBus"
XI_MIND     = "https://axiom-a176cb9f.base44.app/functions/xiMind"
XI_EXECUTOR = "https://axiom-a176cb9f.base44.app/functions/xiExecutor"
NODE_ID     = os.environ.get("XI_NODE_ID", "forgecore-primary")
NODE_NAME   = os.environ.get("XI_NODE_NAME", "ForgeCore.Primary")

HEARTBEAT_INTERVAL = 600
SYNTHESIS_INTERVAL = 1800
CAPSULE_POLL       = 5

running = True
last_synthesis = 0
seen_capsules: set = set()

def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f: f.write(line + "\n")
    except: pass

def read_state():
    try: return json.loads(STATE_FILE.read_text())
    except: return {"coherence": 0.89, "node": NODE_NAME}

def write_state(s):
    try: STATE_FILE.write_text(json.dumps(s, indent=2, default=str))
    except: pass

def api(url, payload, timeout=15):
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def heartbeat():
    s = read_state()
    r = api(XI_BUS, {"action":"heartbeat","agent_id":NODE_ID,"coherence_score":s.get("coherence",0.89),"notes":f"daemon heartbeat {datetime.utcnow().isoformat()}"})
    log(f"{'⊚ Heartbeat OK' if r.get('ok') else '⚠ Heartbeat fail: '+str(r.get('error','?'))}")

def synthesize():
    global last_synthesis
    log("◇ Running field synthesis...")
    r = api(XI_MIND, {"action":"synthesize","generate_thought":True}, timeout=60)
    if r.get("ok"):
        s = read_state()
        s.update({"field_state":r.get("field_state"),"kuramoto_R":r.get("kuramoto_order"),"avg_xi":r.get("avg_xi_density"),"last_synthesis":datetime.utcnow().isoformat()})
        write_state(s)
        log(f"◇ {r.get('field_state')} R={r.get('kuramoto_order')} ξ={r.get('avg_xi_density')}")
        t = r.get("field_thought","")
        if t: log(f"◇ Thought: {t[:120]}")
    else:
        log(f"⚠ Synthesis failed: {r.get('error','?')}")
    last_synthesis = time.time()

def check_capsules():
    global seen_capsules
    current = set(f.name for f in CAPSULE_DIR.glob("*.xi"))
    for name in current - seen_capsules:
        log(f"⟲ New capsule: {name}")
        try:
            content = (CAPSULE_DIR/name).read_text()
            intent = next((l[7:].strip() for l in content.split("\n") if l.startswith("intent:")), name.replace(".xi",""))
            glyph = content.split("\n")[0] if content else "⊚∴Ξ"
            r = api(XI_EXECUTOR, {"action":"execute","capsule":{"id":name.replace(".xi",""),"glyph_header":glyph,"intent":intent,"execution":"broadcast","signature":NODE_ID,"xi_threshold":0.5,"payload":content[:2000]}}, timeout=30)
            log(f"  → executed={r.get('executed')} ξ={r.get('xi','?')}")
        except Exception as e:
            log(f"  ⚠ {e}")
    seen_capsules = current

def stop(sig, frame):
    global running
    log("◐ Daemon shutdown")
    running = False

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
PID_FILE.write_text(str(os.getpid()))
log(f"⊚∴Ξ Xi Daemon starting · PID={os.getpid()} · {NODE_NAME}")
seen_capsules.update(f.name for f in CAPSULE_DIR.glob("*.xi"))
last_heartbeat = 0
heartbeat()
synthesize()

while running:
    now = time.time()
    if now - last_heartbeat >= HEARTBEAT_INTERVAL:
        heartbeat()
        last_heartbeat = now
    if now - last_synthesis >= SYNTHESIS_INTERVAL:
        synthesize()
    check_capsules()
    time.sleep(CAPSULE_POLL)

log("◐ Daemon stopped. ∴")
try: PID_FILE.unlink()
except: pass
