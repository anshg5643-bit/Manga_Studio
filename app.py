"""Fukidashi - multi-page Flask app: auth, analyzer, editors, batch, evaluate, dashboard, pipeline settings.
Run:  python app.py   ->  http://localhost:5000"""
import os, re, io, json, glob, time, uuid, sqlite3, secrets, threading, datetime, collections, importlib.util, sys, zipfile, shutil
from functools import wraps
from flask import (Flask, request, jsonify, session, g, render_template, redirect, send_file, abort, Response)
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.dirname(os.path.abspath(__file__))
INST = os.path.join(ROOT, "instance")


def read_keys(path=os.path.join(ROOT, "api_keys.txt")):
    keys = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip().strip('"').strip("'")
    return keys

KEYS = read_keys()

# Allow Railway environment variables to override local configuration
for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "FLASK_SECRET_KEY", "HF_TOKEN"):
    if os.environ.get(key):
        KEYS[key] = os.environ[key]
if KEYS.get("HF_TOKEN"):
    os.environ["HF_TOKEN"] = KEYS["HF_TOKEN"]

app = Flask(__name__, static_folder=os.path.join(ROOT, "static"), template_folder=os.path.join(ROOT, "templates"))
app.secret_key = KEYS.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(MAX_CONTENT_LENGTH=80 * 1024 * 1024, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_HTTPONLY=True,
                  PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30), TEMPLATES_AUTO_RELOAD=True)
DB = os.path.join(INST, "users.db")
for d in ("uploads", "overlays", "batch"):
    os.makedirs(os.path.join(INST, d), exist_ok=True)
INFER_LOCK = threading.Lock()  # one analysis at a time on a small CPU box
JOBS = {}                      # background jobs: batch + training


# ------------------------------------------------------------------ db
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


with sqlite3.connect(DB) as c:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, pw_hash TEXT,
        google_sub TEXT, marketing INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT, source TEXT, seq_id TEXT,
        created TEXT, updated TEXT, secs REAL, config TEXT, detail TEXT, rejected TEXT, sizes TEXT, src TEXT, edited INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS settings(user_id INTEGER PRIMARY KEY, json TEXT);
    """)
    try:
        c.execute("ALTER TABLE users ADD COLUMN marketing INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

now = lambda: datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"


def user_json(u):
    return dict(id=u["id"], name=u["name"] or u["email"].split("@")[0], email=u["email"], hasPassword=bool(u["pw_hash"]),
                marketing=bool(u["marketing"]), created=u["created"])


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def need_login(fn):
    @wraps(fn)
    def w(*a, **k):
        if not current_user():
            return jsonify(error="Sign in to use this tool."), 401
        return fn(*a, **k)
    return w


FEATURE_META = [
    ("analyzer", "Analyzer", "Upload three pages, read every balloon, then edit the transcript line by line.", ["drag & drop", "inline edit", "restore rejected", "5 export formats"]),
    ("speakers", "Speakers", "Rename, merge, swap and re-cluster characters so names stay consistent across pages.", ["rename", "merge", "swap", "re-cluster"]),
    ("reading-order", "Reading order", "Tune right-to-left logic, drag balloons into place and see the reading path drawn on the page.", ["live preview", "drag reorder", "path overlay"]),
    ("batch", "Batch", "Run a whole folder in the background and download the exact submission JSONL.", ["progress", "format check", "official ids"]),
    ("evaluate", "Evaluate", "Score predictions against labels and inspect every matched and missed line side by side.", ["proxy scorer", "per-sequence", "diff view"]),
    ("history", "History", "Every analysis is saved. Search, rename, compare, bulk export or delete.", ["search", "bulk export", "rename"]),
    ("dashboard", "Dashboard", "Charts for lines, speakers, confidence, speed and the words that appear most.", ["14-day activity", "confidence", "top words"]),
    ("pipeline", "Pipeline", "Tune thresholds, check what models are installed and train the filter on your labels.", ["train filter", "model status", "defaults"]),
]


@app.context_processor
def inject():
    u = current_user()
    return dict(user=user_json(u) if u else None, google_ready=bool(KEYS.get("GOOGLE_CLIENT_ID")),
                FEATURES=[dict(slug=a, title=b, desc=c, tags=d) for a, b, c, d in FEATURE_META])


# ------------------------------------------------------------------ pages
APP_PAGES = {
    "analyzer": ("Analyzer", "Read three pages and edit the result"),
    "speakers": ("Speakers", "Rename, merge and check character labels"),
    "reading-order": ("Reading order", "Tune and fix the order of balloons"),
    "batch": ("Batch", "Run a whole folder and export the submission file"),
    "evaluate": ("Evaluate", "Score predictions against labels"),
    "history": ("History", "Every analysis you have run"),
    "dashboard": ("Dashboard", "Numbers across all your work"),
    "pipeline": ("Pipeline", "Settings, models and training"),
    "account": ("Account", "Profile, password and your data"),
}
FEATURES = ["analyzer", "speakers", "reading-order", "batch", "evaluate", "history", "dashboard", "pipeline"]


@app.get("/")
def home():
    return render_template("home.html", page="home")


@app.get("/features")
def features():
    return render_template("features.html", page="features")


@app.get("/how-it-works")
def how():
    return render_template("how.html", page="how")


@app.get("/login")
def login_page():
    if current_user():
        return redirect("/analyzer")
    return render_template("auth.html", page="login", mode="login")


@app.get("/signup")
def signup_page():
    if current_user():
        return redirect("/analyzer")
    return render_template("auth.html", page="signup", mode="signup")


@app.get("/reset-help")
def reset_help():
    return render_template("reset.html", page="reset")


def _app_page(slug):
    title, sub = APP_PAGES[slug]
    return render_template(f"{slug.replace('-', '_')}.html", page=slug, title=title, sub=sub, app_pages=APP_PAGES)


for _slug in APP_PAGES:
    app.add_url_rule(f"/{_slug}", endpoint=f"page_{_slug}", view_func=(lambda s: (lambda: _app_page(s)))(_slug))


@app.get("/api/config")
def config():
    return jsonify(googleClientId=KEYS.get("GOOGLE_CLIENT_ID", ""))


@app.get("/api/me")
def me():
    u = current_user()
    return jsonify(user=user_json(u) if u else None)


# ------------------------------------------------------------------ auth
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/api/signup")
def signup():
    d = request.get_json(silent=True) or {}
    name, email, pw = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    if not EMAIL.match(email):
        return jsonify(error="Enter a valid email address.", field="email"), 400
    if len(pw) < 8:
        return jsonify(error="Use a password with at least 8 characters.", field="password"), 400
    if "repeat" in d and d["repeat"] != pw:
        return jsonify(error="The two passwords do not match.", field="repeat"), 400
    if db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        return jsonify(error="That email already has an account. Sign in instead.", field="email"), 409
    cur = db().execute("INSERT INTO users(email,name,pw_hash,marketing) VALUES(?,?,?,?)",
                       (email, name[:60], generate_password_hash(pw), int(bool(d.get("marketing")))))
    db().commit()
    session.permanent = True
    session["uid"] = cur.lastrowid
    return jsonify(user=user_json(current_user()))


@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    email, pw = (d.get("email") or "").strip().lower(), d.get("password") or ""
    u = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not u or not u["pw_hash"] or not check_password_hash(u["pw_hash"], pw):
        return jsonify(error="Email or password is wrong. If you signed up with Google, use the Google button."), 401
    session.permanent = bool(d.get("remember"))
    session["uid"] = u["id"]
    return jsonify(user=user_json(u))


@app.post("/api/google")
def google():
    cid = KEYS.get("GOOGLE_CLIENT_ID")
    if not cid:
        return jsonify(error="Google sign-in is not set up. Add GOOGLE_CLIENT_ID to api_keys.txt."), 503
    cred = (request.get_json(silent=True) or {}).get("credential", "")
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as grequests
        info = id_token.verify_oauth2_token(cred, grequests.Request(), cid)
    except Exception as e:
        return jsonify(error=f"Google could not verify this sign-in ({type(e).__name__}). Try again."), 401
    if not info.get("email_verified", False):
        return jsonify(error="Your Google email is not verified."), 401
    email = info["email"].lower()
    u = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if u is None:
        cur = db().execute("INSERT INTO users(email,name,google_sub) VALUES(?,?,?)", (email, info.get("name", ""), info["sub"]))
        db().commit()
        u = db().execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    elif not u["google_sub"]:
        db().execute("UPDATE users SET google_sub=? WHERE id=?", (info["sub"], u["id"])); db().commit()
    session.permanent = True
    session["uid"] = u["id"]
    return jsonify(user=user_json(u))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


# ------------------------------------------------------------------ account
@app.route("/api/account", methods=["PATCH", "DELETE"])
@need_login
def account():
    u = current_user()
    if request.method == "DELETE":
        for r in db().execute("SELECT id FROM analyses WHERE user_id=?", (u["id"],)).fetchall():
            _purge_files(r["id"])
        db().execute("DELETE FROM analyses WHERE user_id=?", (u["id"],))
        db().execute("DELETE FROM settings WHERE user_id=?", (u["id"],))
        db().execute("DELETE FROM users WHERE id=?", (u["id"],)); db().commit()
        session.clear()
        return jsonify(ok=True)
    d = request.get_json(silent=True) or {}
    if "name" in d:
        db().execute("UPDATE users SET name=? WHERE id=?", ((d["name"] or "").strip()[:60], u["id"]))
    if "marketing" in d:
        db().execute("UPDATE users SET marketing=? WHERE id=?", (int(bool(d["marketing"])), u["id"]))
    db().commit()
    return jsonify(user=user_json(current_user()))


@app.post("/api/account/password")
@need_login
def change_password():
    u, d = current_user(), request.get_json(silent=True) or {}
    new = d.get("new") or ""
    if u["pw_hash"] and not check_password_hash(u["pw_hash"], d.get("current") or ""):
        return jsonify(error="Your current password is wrong.", field="current"), 400
    if len(new) < 8:
        return jsonify(error="Use a new password with at least 8 characters.", field="new"), 400
    db().execute("UPDATE users SET pw_hash=? WHERE id=?", (generate_password_hash(new), u["id"])); db().commit()
    return jsonify(ok=True)


# ------------------------------------------------------------------ settings / system
DEFAULTS = dict(keep_threshold=0.5, rtl=True, alpha=1.0, use_panels=True, speaker_mode="alternate", speaker_thr=0.35, backend="classic")
LIMITS = dict(keep_threshold=(0.05, 0.95), alpha=(0.0, 4.0), speaker_thr=(0.05, 1.5))


def clean_cfg(d):
    out = {}
    for k, v in (d or {}).items():
        if k not in DEFAULTS:
            continue
        try:
            if k in LIMITS:
                v = min(max(float(v), LIMITS[k][0]), LIMITS[k][1])
            elif k in ("rtl", "use_panels"):
                v = bool(v) if not isinstance(v, str) else v in ("1", "true", "True")
            elif k == "speaker_mode" and v not in ("alternate", "appearance", "single"):
                continue
            elif k == "backend" and v not in ("classic", "vlm"):
                continue
        except (TypeError, ValueError):
            continue
        out[k] = v
    return out


def user_cfg(overrides=None):
    base = dict(DEFAULTS)
    p = os.path.join(ROOT, "config.json")
    if os.path.exists(p):
        base.update(clean_cfg(json.load(open(p))))
    u = current_user()
    if u:
        r = db().execute("SELECT json FROM settings WHERE user_id=?", (u["id"],)).fetchone()
        if r:
            base.update(clean_cfg(json.loads(r["json"])))
    base.update(clean_cfg(overrides))
    from mangapipe import PipelineConfig
    cfg = PipelineConfig()
    for k, v in base.items():
        setattr(cfg, k, v)
    return cfg


@app.route("/api/settings", methods=["GET", "PUT", "DELETE"])
@need_login
def settings():
    u = current_user()
    if request.method == "PUT":
        db().execute("INSERT INTO settings(user_id,json) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET json=excluded.json",
                     (u["id"], json.dumps(clean_cfg(request.get_json(silent=True)))))
        db().commit()
    elif request.method == "DELETE":
        db().execute("DELETE FROM settings WHERE user_id=?", (u["id"],)); db().commit()
    c = user_cfg()
    return jsonify(config={k: getattr(c, k) for k in DEFAULTS}, defaults=DEFAULTS)


@app.get("/api/system")
@need_login
def system():
    from mangapipe import classifier
    m = classifier.load()
    vlm_dir = os.path.join(ROOT, "models", "qwen_lora")
    has_torch = importlib.util.find_spec("torch") is not None
    try:
        import onnxruntime
        ort = onnxruntime.__version__
    except Exception:
        ort = None
    return jsonify(trainedFilter=bool(m), filterMeta=(m or {}).get("meta", {}).get("cv"), cpu=os.cpu_count(),
                   python=sys.version.split()[0], onnxruntime=ort, torch=has_torch,
                   vlmAdapter=os.path.isdir(vlm_dir), vlmReady=has_torch and os.path.isdir(vlm_dir),
                   googleConfigured=bool(KEYS.get("GOOGLE_CLIENT_ID")))


# ------------------------------------------------------------------ samples
def sample_groups():
    groups, path = {}, os.path.join(ROOT, "sample_dirs.txt")
    if not os.path.exists(path):
        return groups
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            d = line if os.path.isabs(line) else os.path.normpath(os.path.join(ROOT, line))
            seqs = {}
            for s in sorted(glob.glob(os.path.join(d, "*"))):
                imgs = sorted(glob.glob(os.path.join(s, "*.png")) + glob.glob(os.path.join(s, "*.jpg")) + glob.glob(os.path.join(s, "*.jpeg")))
                if len(imgs) >= 3:
                    seqs[os.path.basename(s)] = imgs[:3]
            if seqs:
                groups[os.path.basename(d.rstrip("/\\"))] = seqs
    return groups


def find_sample(sid):
    for seqs in sample_groups().values():
        if sid in seqs:
            return seqs[sid]


@app.get("/api/samples")
@need_login
def samples():
    return jsonify(groups=[dict(name=k, count=len(v), ids=list(v)) for k, v in sample_groups().items()])


# ------------------------------------------------------------------ analyses
def derive_pages(detail):
    return [[dict(speaker=d["speaker"], text=d["text"]) for d in sorted(p, key=lambda d: d["order"])] for p in detail]


def _file(kind, aid, i, ext="bin"):
    return os.path.join(INST, kind, f"{aid}_{i}.{ext}")


def _purge_files(aid):
    for f in glob.glob(os.path.join(INST, "uploads", f"{aid}_*")) + glob.glob(os.path.join(INST, "overlays", f"{aid}_*")):
        try:
            os.remove(f)
        except OSError:
            pass


def row_json(r, full=False):
    detail = json.loads(r["detail"])
    o = dict(id=r["id"], title=r["title"], source=r["source"], seqId=r["seq_id"], created=r["created"], updated=r["updated"],
             secs=r["secs"], edited=bool(r["edited"]), nLines=[len(p) for p in detail], config=json.loads(r["config"] or "{}"))
    if full:
        o.update(detail=detail, pages=derive_pages(detail), rejected=json.loads(r["rejected"] or "[[],[],[]]"),
                 sizes=json.loads(r["sizes"] or "[]"),
                 overlays=[f"/api/analyses/{r['id']}/overlay/{i}.jpg?v={abs(hash(r['updated']))}" for i in range(3)])
    return o


def get_row(aid):
    u = current_user()
    r = db().execute("SELECT * FROM analyses WHERE id=? AND user_id=?", (aid, u["id"])).fetchone()
    if not r:
        abort(404)
    return r


def row_images(r):
    import cv2, numpy as np
    src = json.loads(r["src"] or "null")
    imgs = []
    for i in range(3):
        if src:
            arr = np.fromfile(src[i], np.uint8)
        else:
            arr = np.fromfile(_file("uploads", r["id"], i), np.uint8)
        imgs.append(cv2.imdecode(arr, cv2.IMREAD_COLOR))
    return imgs


def run_pipeline(images, cfg):
    from mangapipe import analyze_sequence
    t = time.time()
    with INFER_LOCK:
        res = analyze_sequence(images, cfg, overlay=False)
    res["secs"] = round(time.time() - t, 2)
    return res


def save_analysis(title, source, seq_id, res, cfg, src=None, blobs=None):
    u = current_user()
    cur = db().execute(
        "INSERT INTO analyses(user_id,title,source,seq_id,created,updated,secs,config,detail,rejected,sizes,src) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (u["id"], title, source, seq_id, now(), now(), res["secs"], json.dumps(res["config"]), json.dumps(res["detail"]),
         json.dumps(res.get("rejected", [[], [], []])), json.dumps(res.get("sizes", [])), json.dumps(src) if src else None))
    db().commit()
    aid = cur.lastrowid
    if blobs:
        for i, b in enumerate(blobs):
            open(_file("uploads", aid, i), "wb").write(b)
    return aid


def full_row(aid):
    return row_json(db().execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone(), full=True)


@app.post("/api/analyze")
@need_login
def analyze():
    import cv2, numpy as np
    files = [request.files.get(f"page{i}") for i in (1, 2, 3)]
    if not all(files):
        return jsonify(error="Add all three pages (page1, page2, page3)."), 400
    blobs = [f.read() for f in files]
    for b in blobs:
        if cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) is None:
            return jsonify(error="One of the files is not a readable image (use PNG or JPG)."), 400
    cfg = user_cfg({k: request.form.get(k) for k in DEFAULTS if request.form.get(k) is not None})
    try:
        res = run_pipeline(blobs, cfg)
    except Exception as e:
        app.logger.exception("analyze failed")
        return jsonify(error=f"Analysis failed: {type(e).__name__}: {e}"), 500
    title = (request.form.get("title") or "").strip() or "Upload " + datetime.datetime.now().strftime("%b %d, %H:%M")
    aid = save_analysis(title, "upload", None, res, cfg, blobs=blobs)
    return jsonify(analysis=full_row(aid), usedTrainedFilter=res["used_trained_filter"])


@app.post("/api/analyze_sample")
@need_login
def analyze_sample():
    d = request.get_json(silent=True) or {}
    sid = d.get("id", "")
    paths = find_sample(sid)
    if not paths:
        return jsonify(error="Unknown sample sequence."), 404
    cfg = user_cfg(d.get("config"))
    try:
        res = run_pipeline(paths, cfg)
    except Exception as e:
        app.logger.exception("analyze_sample failed")
        return jsonify(error=f"Analysis failed: {type(e).__name__}: {e}"), 500
    aid = save_analysis(sid, "sample", sid, res, cfg, src=paths)
    return jsonify(analysis=full_row(aid), usedTrainedFilter=res["used_trained_filter"])


@app.get("/api/analyses")
@need_login
def analyses():
    rows = db().execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id DESC", (current_user()["id"],)).fetchall()
    return jsonify(analyses=[row_json(r) for r in rows])


@app.route("/api/analyses/<int:aid>", methods=["GET", "PATCH", "DELETE"])
@need_login
def analysis(aid):
    r = get_row(aid)
    if request.method == "DELETE":
        _purge_files(aid)
        db().execute("DELETE FROM analyses WHERE id=?", (aid,)); db().commit()
        return jsonify(ok=True)
    if request.method == "PATCH":
        d = request.get_json(silent=True) or {}
        if "title" in d:
            db().execute("UPDATE analyses SET title=? WHERE id=?", ((d["title"] or "").strip()[:80] or r["title"], aid))
        if "detail" in d:
            det = []
            for p in (d["detail"] + [[], [], []])[:3]:
                det.append([dict(speaker=str(l.get("speaker") or "char1")[:40], text=str(l.get("text") or "").strip(), order=i + 1,
                                 p_keep=float(l.get("p_keep", 1.0)), box=l.get("box")) for i, l in enumerate(p) if str(l.get("text") or "").strip()])
            db().execute("UPDATE analyses SET detail=?, edited=1, updated=? WHERE id=?", (json.dumps(det), now(), aid))
            if "rejected" in d:
                db().execute("UPDATE analyses SET rejected=? WHERE id=?", (json.dumps(d["rejected"]), aid))
            for f in glob.glob(os.path.join(INST, "overlays", f"{aid}_*")):
                os.remove(f)
        db().commit()
        return jsonify(analysis=full_row(aid))
    return jsonify(analysis=row_json(r, full=True))


@app.get("/api/analyses/<int:aid>/overlay/<int:i>.jpg")
@need_login
def overlay(aid, i):
    r = get_row(aid)
    if not 0 <= i < 3:
        abort(404)
    show_rej = request.args.get("rejected", "1") == "1"
    f = _file("overlays", aid, f"{i}{'' if show_rej else 'n'}", "jpg")
    if not os.path.exists(f):
        from mangapipe.pipeline import render_overlay_detail
        det, rej = json.loads(r["detail"])[i], json.loads(r["rejected"] or "[[],[],[]]")[i]
        open(f, "wb").write(render_overlay_detail(row_images(r)[i], det, rej, show_rejected=show_rej))
    resp = send_file(f, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp


@app.post("/api/analyses/<int:aid>/rerun")
@need_login
def rerun(aid):
    """Re-run the pipeline on the stored images with new settings. save=true overwrites the analysis, otherwise preview only."""
    import base64
    from mangapipe.pipeline import render_overlay_detail
    r = get_row(aid)
    d = request.get_json(silent=True) or {}
    cfg = user_cfg(d.get("config"))
    try:
        res = run_pipeline(row_images(r), cfg)
    except Exception as e:
        return jsonify(error=f"Analysis failed: {type(e).__name__}: {e}"), 500
    if d.get("save"):
        db().execute("UPDATE analyses SET detail=?, rejected=?, config=?, secs=?, edited=0, updated=? WHERE id=?",
                     (json.dumps(res["detail"]), json.dumps(res["rejected"]), json.dumps(res["config"]), res["secs"], now(), aid))
        db().commit()
        for f in glob.glob(os.path.join(INST, "overlays", f"{aid}_*")):
            os.remove(f)
        return jsonify(analysis=full_row(aid))
    imgs = row_images(r)
    ov = ["data:image/jpeg;base64," + base64.b64encode(render_overlay_detail(imgs[i], res["detail"][i], res["rejected"][i])).decode() for i in range(3)]
    return jsonify(preview=dict(detail=res["detail"], rejected=res["rejected"], overlays=ov, config=res["config"], secs=res["secs"], sizes=res["sizes"]))


@app.get("/api/export")
@need_login
def export_all():
    """Task-format JSONL of selected analyses (?ids=1,2,3) or all."""
    ids = [int(x) for x in request.args.get("ids", "").split(",") if x.strip().isdigit()]
    rows = db().execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id", (current_user()["id"],)).fetchall()
    out = []
    for r in rows:
        if ids and r["id"] not in ids:
            continue
        out.append(json.dumps(dict(sequence_id=r["seq_id"] or f"upload_{r['id']}", pages=derive_pages(json.loads(r["detail"]))), ensure_ascii=False))
    return Response("\n".join(out) + ("\n" if out else ""), mimetype="application/x-ndjson",
                    headers={"Content-Disposition": "attachment; filename=fukidashi_export.jsonl"})


# ------------------------------------------------------------------ stats / dashboard
@app.get("/api/stats")
@need_login
def stats():
    rows = db().execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id", (current_user()["id"],)).fetchall()
    per_page, speakers, conf, secs, per_day = [0, 0, 0], collections.Counter(), [], [], collections.Counter()
    words = collections.Counter()
    for r in rows:
        det = json.loads(r["detail"])
        for i, p in enumerate(det):
            per_page[i] += len(p)
            for l in p:
                speakers[l["speaker"]] += 1; conf.append(l.get("p_keep", 1.0))
                for w in re.findall(r"[A-Za-z']{4,}", l["text"].lower()):
                    words[w] += 1
        secs.append(r["secs"] or 0); per_day[(r["created"] or "")[:10]] += 1
    n = len(rows)
    today = datetime.date.today()
    days = [(today - datetime.timedelta(days=k)).isoformat() for k in range(13, -1, -1)]
    bins = [0] * 5
    for c in conf:
        bins[min(4, int(c * 5))] += 1
    total_lines = sum(per_page)
    recent = [row_json(r) for r in rows[-6:]][::-1]
    return jsonify(totals=dict(analyses=n, lines=total_lines, edited=sum(1 for r in rows if r["edited"]),
                               avgSecs=round(sum(secs) / n, 1) if n else 0, linesPerPage=[round(x / n, 1) if n else 0 for x in per_page],
                               avgConf=round(sum(conf) / len(conf), 3) if conf else 0),
                   days=[dict(day=d, n=per_day.get(d, 0)) for d in days], speakers=speakers.most_common(8), confBins=bins,
                   topWords=words.most_common(10), recent=recent, sources=dict(collections.Counter(r["source"] for r in rows)))


# ------------------------------------------------------------------ batch (run a folder -> submission jsonl)
def _job_owner_ok(job):
    u = current_user()
    return job and u and job["user"] == u["id"]


def _images_in_folder(folder):
    exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
    return sorted(str(p) for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in exts)


def _sequences_from_zip(upload, jid):
    """Safely unpack image files only, then infer one sequence per folder."""
    base = os.path.join(INST, "batch_uploads", jid)
    os.makedirs(base, exist_ok=True)
    try:
        zf = zipfile.ZipFile(upload)
    except Exception:
        raise ValueError("Upload a valid .zip file containing 15 sequence folders.")
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    total_bytes = 0
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if not parts or any(p == ".." for p in parts):
                continue
            if os.path.splitext(parts[-1])[1].lower() not in image_exts:
                continue
            total_bytes += info.file_size
            if total_bytes > 250 * 1024 * 1024:
                raise ValueError("The uncompressed images exceed 250 MB. Please upload a smaller ZIP.")
            dest = os.path.join(base, *parts)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
    image_paths = [str(p) for p in Path(base).rglob("*") if p.is_file() and p.suffix.lower() in image_exts]
    if not image_paths:
        raise ValueError("No PNG, JPG, JPEG, WEBP or BMP images were found in the ZIP.")
    # Remove a single common wrapper directory, if the ZIP contains one.
    rels = [os.path.relpath(p, base).split(os.sep) for p in image_paths]
    if rels and all(len(parts) > 1 for parts in rels) and len({parts[0] for parts in rels}) == 1:
        wrapper = rels[0][0]
        base = os.path.join(base, wrapper)
        image_paths = [str(p) for p in Path(base).rglob("*") if p.is_file() and p.suffix.lower() in image_exts]
    # Prefer one top-level folder per sequence, even when each sequence has a nested pages/ folder.
    top_level = collections.defaultdict(list)
    for p in image_paths:
        rel = os.path.relpath(p, base).split(os.sep)
        if len(rel) >= 2:
            top_level[os.path.join(base, rel[0])].append(p)
    candidates = {d: sorted(v) for d, v in top_level.items() if len(v) >= 3}
    if len(candidates) != 15:
        # Fallback: sequence folders directly contain the page images.
        by_dir = collections.defaultdict(list)
        for p in image_paths:
            by_dir[os.path.dirname(p)].append(p)
        candidates = {d: sorted(v) for d, v in by_dir.items() if len(v) >= 3}
        # Discard parent candidates when a deeper candidate already represents that sequence.
        dirs = list(candidates)
        for d in dirs:
            if any(other != d and os.path.commonpath([d, other]) == d for other in dirs):
                del candidates[d]
    seqs = {}
    for d, imgs in sorted(candidates.items()):
        sid = os.path.basename(d.rstrip(os.sep))
        if sid in seqs:
            sid = os.path.relpath(d, base).replace(os.sep, "_")
        if len(imgs) < 3:
            continue
        seqs[sid] = imgs[:3]
    if len(seqs) != 15:
        raise ValueError(f"Found {len(seqs)} sequence folders with at least 3 images; expected exactly 15. Put each sequence's 3 pages inside its own folder, then ZIP the parent folder.")
    return seqs, base


@app.post("/api/batch/start")
@need_login
def batch_start():
    jid = uuid.uuid4().hex[:10]
    upload = request.files.get("zip_file")
    uploaded_zip = bool(upload and upload.filename)
    upload_root = None
    if uploaded_zip:
        if not upload.filename.lower().endswith(".zip"):
            return jsonify(error="Please upload a .zip file containing your 15 sequences."), 400
        try:
            seqs, upload_root = _sequences_from_zip(upload.stream, jid)
        except ValueError as e:
            shutil.rmtree(os.path.join(INST, "batch_uploads", jid), ignore_errors=True)
            return jsonify(error=str(e)), 400
        group = "uploaded_zip"
    else:
        group = request.form.get("group", "")
        seqs = sample_groups().get(group)
        if not seqs:
            return jsonify(error="Upload a ZIP of 15 sequence folders or choose a dataset folder."), 400
    ids = list(seqs)
    f = request.files.get("ids_file")
    if f and f.filename:
        try:
            wanted = [json.loads(l)["sequence_id"] for l in f.read().decode("utf-8").splitlines() if l.strip()]
        except Exception:
            return jsonify(error="That ids file is not valid JSONL with a sequence_id on each line."), 400
        # For uploaded ZIPs, use folder names as IDs by default; an official ID list can only
        # be applied when its IDs correspond to the folder names, preventing silent remapping.
        if uploaded_zip and len(wanted) != 15:
            return jsonify(error="For a ZIP upload, the optional ID list must contain exactly 15 sequence IDs."), 400
        missing = [w for w in wanted if w not in seqs]
        if missing:
            return jsonify(error=f"{len(missing)} id(s) in the file were not found in this ZIP/folder, e.g. {missing[0]}.") , 400
        ids = wanted
    limit = request.form.get("limit", type=int)
    # A ZIP upload always yields 15 prediction lines; limit only applies to local folders.
    if limit and limit > 0 and not uploaded_zip:
        ids = ids[:limit]
    cfg = user_cfg({k: request.form.get(k) for k in DEFAULTS if request.form.get(k) is not None})
    job = dict(user=current_user()["id"], kind="batch", status="running", total=len(ids), done=0, rows=[], errors=[], started=time.time(),
               group=group, file=os.path.join(INST, "batch", f"{jid}.jsonl"), upload_root=upload_root)
    JOBS[jid] = job

    def work():
        from mangapipe import analyze_sequence
        out = []
        for sid in ids:
            try:
                with INFER_LOCK:
                    t = time.time(); res = analyze_sequence(seqs[sid], cfg)
                pages = (res["pages"] + [[], [], []])[:3]
                out.append(dict(sequence_id=sid, pages=pages))
                job["rows"].append(dict(id=sid, lines=[len(p) for p in pages], secs=round(time.time() - t, 1)))
            except Exception as e:
                job["errors"].append(f"{sid}: {type(e).__name__}: {e}")
                out.append(dict(sequence_id=sid, pages=[[], [], []]))
            job["done"] += 1
        with open(job["file"], "w", encoding="utf-8") as fh:
            for r in out:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        job["status"] = "done"; job["secs"] = round(time.time() - job["started"], 1)
    threading.Thread(target=work, daemon=True).start()
    return jsonify(job=jid, total=len(ids))

def validate_submission(rows):
    issues = []
    for i, r in enumerate(rows):
        if "sequence_id" not in r:
            issues.append(f"line {i + 1}: missing sequence_id"); continue
        pg = r.get("pages")
        if not isinstance(pg, list) or len(pg) != 3:
            issues.append(f"{r['sequence_id']}: needs exactly 3 pages"); continue
        for pi, p in enumerate(pg):
            for l in p:
                if not isinstance(l, dict) or not str(l.get("speaker", "")).strip() or not str(l.get("text", "")).strip():
                    issues.append(f"{r['sequence_id']} page {pi + 1}: a line is missing speaker or text"); break
    ids = [r.get("sequence_id") for r in rows]
    if len(set(ids)) != len(ids):
        issues.append("duplicate sequence_id values")
    return issues


@app.get("/api/batch/<jid>")
@need_login
def batch_status(jid):
    job = JOBS.get(jid)
    if not _job_owner_ok(job):
        abort(404)
    out = dict(status=job["status"], total=job["total"], done=job["done"], rows=job["rows"][-300:], errors=job["errors"][:20], secs=job.get("secs"))
    if job["status"] == "done":
        rows = [json.loads(l) for l in open(job["file"], encoding="utf-8") if l.strip()]
        out["issues"] = validate_submission(rows)
        out["totalLines"] = sum(len(p) for r in rows for p in r["pages"])
        out["emptyPages"] = sum(1 for r in rows for p in r["pages"] if not p)
    return jsonify(out)


@app.get("/api/batch/<jid>/download")
@need_login
def batch_download(jid):
    job = JOBS.get(jid)
    if not _job_owner_ok(job) or job["status"] != "done":
        abort(404)
    return send_file(job["file"], mimetype="application/x-ndjson", as_attachment=True, download_name="manga_predictions.jsonl")


# ------------------------------------------------------------------ evaluate (local proxy scorer)
def _read_jsonl_upload(f, what):
    try:
        rows = [json.loads(l) for l in f.read().decode("utf-8").splitlines() if l.strip()]
        return {r["sequence_id"]: r["pages"] for r in rows}
    except Exception:
        raise ValueError(f"{what} is not valid JSONL (one object per line with sequence_id and pages).")


@app.post("/api/evaluate")
@need_login
def evaluate():
    from mangapipe.scoring import score_all, match
    lf, pf = request.files.get("labels"), request.files.get("predictions")
    if not lf:
        return jsonify(error="Add a labels.jsonl file."), 400
    try:
        refs = _read_jsonl_upload(lf, "labels")
        if pf:
            preds = _read_jsonl_upload(pf, "predictions")
        else:  # fall back to this account's history, matched by sequence id
            preds = {}
            for r in db().execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id", (current_user()["id"],)).fetchall():
                if r["seq_id"]:
                    preds[r["seq_id"]] = derive_pages(json.loads(r["detail"]))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    common = [s for s in refs if s in preds]
    if not common:
        return jsonify(error="No sequence ids in common between labels and predictions."), 400
    mean, rows = score_all({s: preds[s] for s in common}, {s: refs[s] for s in common})
    detail = {}
    for s in common:
        pairs = []
        for pi in range(3):
            pp, rr = (preds[s] + [[], [], []])[pi], (refs[s] + [[], [], []])[pi]
            pairs.append([[i, j, round(sc, 2)] for i, j, sc in match(pp, rr)])
        detail[s] = dict(pred=(preds[s] + [[], [], []])[:3], ref=(refs[s] + [[], [], []])[:3], pairs=pairs)
    return jsonify(mean=mean, rows=[dict(id=s, **rows[s]) for s in common], detail=detail,
                   skipped=dict(labelsOnly=len(refs) - len(common), predsOnly=len(preds) - len(common)))


# ------------------------------------------------------------------ train the keep-filter from labels
@app.post("/api/train")
@need_login
def train():
    group = request.form.get("group", "")
    seqs, f = sample_groups().get(group), request.files.get("labels")
    if not seqs or not f:
        return jsonify(error="Choose a dataset folder and a labels.jsonl file."), 400
    try:
        refs = _read_jsonl_upload(f, "labels")
    except ValueError as e:
        return jsonify(error=str(e)), 400
    hits = [s for s in refs if s in seqs]
    if len(hits) < 5:
        return jsonify(error=f"Only {len(hits)} label ids match folders in this dataset. Sequence ids must equal the folder names."), 400
    jid = uuid.uuid4().hex[:10]
    job = dict(user=current_user()["id"], kind="train", status="running", total=len(hits), done=0, report=None, error=None)
    JOBS[jid] = job

    def work():
        from mangapipe.train import train_filter
        try:
            def prog(i, n):
                job["done"] = i
            job["report"] = train_filter(seqs, {s: refs[s] for s in hits}, progress=prog)
            job["status"] = "done"
        except Exception as e:
            job["status"] = "error"; job["error"] = f"{type(e).__name__}: {e}"
    threading.Thread(target=work, daemon=True).start()
    return jsonify(job=jid)


@app.get("/api/train/<jid>")
@need_login
def train_status(jid):
    job = JOBS.get(jid)
    if not _job_owner_ok(job):
        abort(404)
    return jsonify({k: job[k] for k in ("status", "total", "done", "report", "error")})


if __name__ == "__main__":
    print("Google sign-in:", "configured" if KEYS.get("GOOGLE_CLIENT_ID") else "NOT configured (edit api_keys.txt)")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
