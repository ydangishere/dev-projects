"""
DXA - Trợ lý sửa xe máy dựng từ kênh YouTube "y dang" (@ydang7076).

5 tầng tri thức:
  1. Vector   : TF-IDF (âm tiết + n-gram ký tự) + SVD.  Thay bằng bge-m3 / Gemini embedding khi có mạng.
  2. Keyword  : BM25 tự viết (không cần thư viện ngoài).
  3. Graph    : networkx, Triệu chứng -> Nguyên nhân -> Cách sửa -> Phụ tùng / Dụng cụ, mỗi cạnh gắn video + giây.
  4. SQL      : SQLite, bảng videos / chunks / cases / parts / tools / specs.
  5. Trả lời  : gộp các tầng, luôn kèm link YouTube nhảy đúng giây.

Dùng:
  python dxa.py build
  python dxa.py ask "xe để lâu bị chảy xăng bình xăng con"
  python dxa.py sql "select * from specs"
"""
import json, math, re, sqlite3, sys, unicodedata, pickle
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "index"

# ---------------------------------------------------------------- chuẩn hoá tiếng Việt
# Từ đồng nghĩa / cách gọi dân dã -> dạng chuẩn trong kho. Thợ duyệt và bổ sung dần.
SYNONYMS = {
    "tràn xăng": "chảy xăng", "rỉ xăng": "chảy xăng", "xì xăng": "chảy xăng", "nhỏ xăng": "chảy xăng",
    "bình xăng con": "bình xăng con", "chế hòa khí": "bình xăng con", "carburetor": "bình xăng con", "bxc": "bình xăng con",
    "hộp lọc gió": "bao tử", "lọc gió": "bao tử lọc gió", "pô e": "bao tử", "po e": "bao tử",
    "cổ hút": "co xăng", "cổ xăng": "co xăng", "họng hút": "họng gió",
    "gắp": "gấp", "càng sau": "gấp", "relay": "rơ le", "role": "rơ le", "rơle": "rơ le",
    "xinhan": "xi nhan", "xi-nhan": "xi nhan", "đèn phá sương": "đèn trợ sáng", "đèn bi cầu": "đèn trợ sáng",
    "xú páp": "xupap", "xú bắp": "xupap", "supap": "xupap", "valve": "xupap",
    "cò mổ": "cò", "cò xupap": "cò", "rocker": "cò",
    "bu gi": "bugi", "buji": "bugi", "spark plug": "bugi",
    "ga không đều": "ga không đều", "hụt ga": "mất ga", "hụt hơi": "mất ga", "đuối": "mất ga",
    "giật cục": "giật", "rung": "đờn",
    "gioăng": "ron", "joint": "ron", "đầu quy lát": "đầu culass", "đầu bò": "đầu culass", "culass": "đầu culass",
    "xích cam": "sên cam", "cam căng": "sên cam căng",
}

def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")

def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text.lower())
    for k, v in sorted(SYNONYMS.items(), key=lambda kv: -len(kv[0])):
        t = t.replace(k, v)
    return t

def tokens(text: str):
    """Âm tiết + bigram âm tiết, cả bản có dấu lẫn không dấu (người dùng hay gõ không dấu)."""
    t = normalize(text)
    syl = re.findall(r"[0-9a-zà-ỹđ\.]+", t)
    syl = [s.strip(".") for s in syl if s.strip(".")]
    out = syl + [a + "_" + b for a, b in zip(syl, syl[1:])]
    return out + [strip_accents(x) for x in out]

def yt_link(vid, t):
    return f"https://www.youtube.com/watch?v={vid}&t={int(t)}s"

def mmss(t):
    return f"{int(t)//60}:{int(t)%60:02d}"

def from_video(c):
    """Case lấy từ video có video_id + giây; case thợ nhập trên tab Bổ sung kiến thức thì không."""
    return bool(c.get("video_id"))

def origin(videos, c):
    """(tiêu đề nguồn, thời điểm, link) của một case.
    Case thợ nhập: có link YouTube thợ gắn thì mở video đó đúng giây, không gắn thì không có link."""
    if from_video(c):
        return videos[c["video_id"]]["title"], mmss(c["t"]), yt_link(c["video_id"], c["t"])
    title = f"Thợ nhập ngày {c.get('created_at', '')[:10]}".strip()
    if c.get("yt_id"):
        t = int(c.get("yt_t") or 0)
        return f"{title}, video thợ gắn", mmss(t), yt_link(c["yt_id"], t)
    return title, "", ""

# ---------------------------------------------------------------- nạp dữ liệu
def load_videos():
    rows = [l.split("\t") for l in (DATA / "videos.tsv").read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
    return {r[0]: {"video_id": r[0], "title": r[1], "duration": r[2], "topic": r[3],
                   "status": r[4] if len(r) > 4 else "ok"} for r in rows}

def load_cases():
    cases = []
    for f in sorted(DATA.glob("knowledge*.json")):
        cases += json.loads(f.read_text(encoding="utf-8"))["cases"]
    # case bị thợ đánh "Sai" vẫn nằm trong file (để truy vết) nhưng không vào kho
    return [c for c in cases if c.get("status") != "rejected"]

def load_chunks(videos):
    chunks = []
    for vid in videos:
        if not (DATA / "clean" / f"{vid}.txt").exists():
            continue
        lines = (DATA / "clean" / f"{vid}.txt").read_text(encoding="utf-8").splitlines()
        parsed = [(int(m.group(1)), m.group(2).strip()) for m in (re.match(r"\[(\d+)\]\s*(.*)", l) for l in lines) if m]
        for i, (t, txt) in enumerate(parsed):
            end = parsed[i + 1][0] if i + 1 < len(parsed) else None
            chunks.append({"chunk_id": f"{vid}#{t}", "video_id": vid, "start": t, "end": end,
                           "title": videos[vid]["title"], "text": txt})
    return chunks

# ---------------------------------------------------------------- tầng 2: BM25
class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=float)
        self.avg = self.len.mean()
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, q):
        s = np.zeros(len(self.tf))
        for t in set(q):
            if t not in self.idf:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t, 0)
                if f:
                    s[i] += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return s

# ---------------------------------------------------------------- tầng 1: Vector (bản thay thế offline)
def _prep(s):
    return strip_accents(normalize(s))

class Vectorizer:
    """TF-IDF n-gram ký tự + SVD (LSA). Giao diện encode() giữ nguyên khi đổi sang model embedding thật."""
    def fit(self, texts):
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), preprocessor=_prep, sublinear_tf=True)
        X = self.tfidf.fit_transform(texts)
        self.svd = TruncatedSVD(n_components=min(64, X.shape[0] - 1), random_state=0).fit(X)
        return self

    def encode(self, texts):
        V = self.svd.transform(self.tfidf.transform(texts))
        return V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-9)

# ---------------------------------------------------------------- tầng 3: Graph
def build_graph(cases, videos):
    G = nx.MultiDiGraph()
    def node(kind, name):
        nid = f"{kind}:{name}"
        G.add_node(nid, kind=kind, name=name)
        return nid
    for c in cases:
        src = {"video_id": c.get("video_id") or "", "t": c.get("t") or 0, "case": c["id"], "source": c.get("source", "video")}
        s, ca, f = node("TrieuChung", c["symptom"]), node("NguyenNhan", c["cause"]), node("CachSua", c["fix"])
        G.add_edge(s, ca, rel="DO", **src)
        G.add_edge(ca, f, rel="SUA_BANG", **src)
        G.add_edge(s, node("HeThong", c["system"]), rel="THUOC", **src)
        for p in c["parts"]:
            G.add_edge(f, node("PhuTung", p), rel="LIEN_QUAN", **src)
        for tl in c["tools"]:
            G.add_edge(f, node("DungCu", tl), rel="DUNG", **src)
        for v in c["vehicles"]:
            G.add_edge(s, node("DongXe", v), rel="GAP_O", **src)
        if from_video(c):
            G.add_edge(f, node("Video", videos[c["video_id"]]["title"]), rel="NGUON", **src)
        else:
            G.add_edge(f, node("Tho", c.get("author") or "thợ"), rel="NGUON", **src)
    return G

# ---------------------------------------------------------------- tầng 4: SQL
SCHEMA = """
create table videos(video_id text primary key, title text, duration text, topic text);
create table chunks(chunk_id text primary key, video_id text, start int, end int, text text);
create table cases(case_id text primary key, video_id text, t int, system text, symptom text, cause text, fix text, reviewed int);
create table parts(case_id text, part text);
create table tools(case_id text, tool text);
create table vehicles(case_id text, vehicle text);
create table specs(case_id text, name text, value text, unit text);
create table warnings(case_id text, warning text);
"""

def build_sql(path, videos, chunks, cases):
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.executemany("insert into videos values(?,?,?,?)", [(v["video_id"], v["title"], v["duration"], v["topic"]) for v in videos.values()])
    db.executemany("insert into chunks values(?,?,?,?,?)", [(c["chunk_id"], c["video_id"], c["start"], c["end"], c["text"]) for c in chunks])
    for c in cases:
        db.execute("insert into cases values(?,?,?,?,?,?,?,?)", (c["id"], c["video_id"], c["t"], c["system"], c["symptom"], c["cause"], c["fix"], int(c["reviewed"])))
        db.executemany("insert into parts values(?,?)", [(c["id"], p) for p in c["parts"]])
        db.executemany("insert into tools values(?,?)", [(c["id"], p) for p in c["tools"]])
        db.executemany("insert into vehicles values(?,?)", [(c["id"], p) for p in c["vehicles"]])
        db.executemany("insert into specs values(?,?,?,?)", [(c["id"], s["name"], s["value"], s["unit"]) for s in c["specs"]])
        db.executemany("insert into warnings values(?,?)", [(c["id"], w) for w in c["warnings"]])
    db.commit()
    db.close()

# ---------------------------------------------------------------- build
def build():
    OUT.mkdir(exist_ok=True)
    videos = load_videos()
    chunks = load_chunks(videos)
    cases = load_cases()

    chunk_text = [c["title"] + ". " + c["text"] for c in chunks]
    case_text = [f'{c["symptom"]}. {c["cause"]}. {c["fix"]}. {" ".join(c["parts"])}' for c in cases]

    vec = Vectorizer().fit(chunk_text + case_text)
    G = build_graph(cases, videos)
    build_sql(OUT / "dxa.sqlite", videos, chunks, cases)
    nx.write_graphml(G, OUT / "graph.graphml")

    state = {
        "videos": videos, "chunks": chunks, "cases": cases,
        "bm25_chunks": BM25([tokens(t) for t in chunk_text]),
        "bm25_cases": BM25([tokens(t) for t in case_text]),
        "vec": vec, "E_chunks": vec.encode(chunk_text), "E_cases": vec.encode(case_text),
        "graph": G,
    }
    with open(OUT / "state.pkl", "wb") as f:
        pickle.dump(state, f)
    print(f"videos={len(videos)} chunks={len(chunks)} cases={len(cases)} "
          f"graph_nodes={G.number_of_nodes()} graph_edges={G.number_of_edges()}")

# ---------------------------------------------------------------- truy vấn
def _load():
    with open(OUT / "state.pkl", "rb") as f:
        return pickle.load(f)  # noqa: S301 - state.pkl do chính DXA tạo khi build, không nhận từ người dùng

def rrf(rank_lists, k=60):
    """Reciprocal Rank Fusion: gộp thứ hạng từ nhiều tầng."""
    score = defaultdict(float)
    for ranks in rank_lists:
        for r, i in enumerate(ranks):
            score[i] += 1 / (k + r)
    return sorted(score, key=lambda i: -score[i])

# Câu hỏi được coi là "có trong kho" khi đủ CẢ HAI điều kiện (đo trên eval.py, chỉnh lại mỗi lần thêm video):
#   1. BM25 cao nhất >= MIN_BM25          -> câu hỏi khớp đủ nhiều chữ với một case
#   2. Độ phủ chữ hiếm >= MIN_COVER       -> những chữ HIẾM trong câu hỏi (vd "lốp", "phanh") phải có trong case trả lời
#      Chữ hỏi chung chung ("cách", "dùng", "làm", "gì") không tính: vd "cách đấu đèn báo xi nhan khi không dùng
#      đồng hồ km" từng bị từ chối dù đã tìm đúng C32, chỉ vì "cách" và "dùng" bị đếm là chữ thiếu.
MIN_BM25 = 12.0
MIN_COVER = 0.6
# Vùng "gần đúng": khớp chữ rất mạnh (BM25 cao) nhưng thiếu vài chữ hiếm. DXA vẫn trả lời bằng case gần nhất,
# ghi rõ là câu trả lời gần nhất, và lưu câu hỏi để thợ bổ sung. Đo trên eval.py: 8 câu ngoài phạm vi có BM25
# cao nhất 19.3, câu trong phạm vi thấp nhất 46, nên ngưỡng 25 nằm giữa hai nhóm.
NEAR_BM25 = 25.0
NEAR_COVER = 0.45
_STOP_SCOPE = None

def _syl(t):
    return [w for w in re.findall(r"[0-9a-z]+", strip_accents(normalize(t))) if w not in _STOP_SCOPE]

def rare_word_cover(state, q, case_idx):
    global _STOP_SCOPE
    if _STOP_SCOPE is None:
        _STOP_SCOPE = {strip_accents(w) for w in "bị có không là thì cho khi được mà và của như thế nào sao một xe cách dùng làm gì".split()}
    if "_scope_docs" not in state:
        docs = [set(_syl(f'{c["symptom"]} {c["cause"]} {c["fix"]} {" ".join(c["parts"])} {" ".join(c["vehicles"])}')) for c in state["cases"]]
        df = Counter(w for d in docs for w in d)
        state["_scope_docs"], state["_scope_df"] = docs, df
    docs, df, n = state["_scope_docs"], state["_scope_df"], len(state["cases"])
    idf = lambda w: math.log((n + 1) / (df.get(w, 0) + 0.5))
    qs = set(_syl(q))
    total = sum(idf(w) for w in qs)
    return sum(idf(w) for w in qs if w in docs[case_idx]) / total if total else 0.0

def scope_level(state, q):
    """'in' = có trong kho, 'near' = gần đúng (trả lời bằng case gần nhất, có ghi chú), 'out' = từ chối."""
    b = state["bm25_cases"].scores(tokens(q))
    top, cover = float(b.max()), rare_word_cover(state, q, int(np.argmax(b)))
    if top >= MIN_BM25 and cover >= MIN_COVER:
        return "in"
    if top >= NEAR_BM25 and cover >= NEAR_COVER:
        return "near"
    return "out"

def in_scope(state, q):
    return scope_level(state, q) == "in"

def search(state, q, top=5):
    qt = tokens(q)
    qv = state["vec"].encode([q])[0]

    def hybrid(bm, E, n):
        b = bm.scores(qt)
        v = E @ qv
        ranks_b = [i for i in np.argsort(-b) if b[i] > 0][:20]
        ranks_v = list(np.argsort(-v))[:20]
        fused = rrf([ranks_b, ranks_v])
        return [(i, float(b[i]), float(v[i])) for i in fused[:n]]

    return hybrid(state["bm25_cases"], state["E_cases"], 3), hybrid(state["bm25_chunks"], state["E_chunks"], top)

def graph_context(state, case):
    """Từ triệu chứng, đi theo graph để lấy mọi nguyên nhân / cách sửa khác có cùng phụ tùng."""
    G = state["graph"]
    related = set()
    for p in case["parts"]:
        pid = f"PhuTung:{p}"
        if pid in G:
            for fix_node, _, d in G.in_edges(pid, data=True):
                if d["case"] != case["id"]:
                    related.add(d["case"])
    by_id = {c["id"]: c for c in state["cases"]}
    return [by_id[r] for r in sorted(related)]

def ask(q):
    state = _load()
    case_hits, chunk_hits = search(state, q)
    cases, chunks, videos = state["cases"], state["chunks"], state["videos"]

    lines = [f"Câu hỏi: {q}", ""]
    if not case_hits or not in_scope(state, q):
        lines.append("Chưa có kiến thức này trong các video đã nạp. Không đoán, cần thợ trả lời hoặc nạp thêm video.")
        return "\n".join(lines)

    best = cases[case_hits[0][0]]
    lines += [
        f"Triệu chứng gần nhất: {best['symptom']}",
        f"Nguyên nhân: {best['cause']}",
        f"Cách sửa: {best['fix']}",
    ]
    if best["parts"]:
        lines.append("Phụ tùng: " + ", ".join(best["parts"]))
    if best["tools"]:
        lines.append("Dụng cụ: " + ", ".join(best["tools"]))
    for s in best["specs"]:
        lines.append(f"Thông số: {s['name']} = {s['value']} {s['unit']}")
    for w in best["warnings"]:
        lines.append(f"Lưu ý: {w}")
    title, when, link = origin(videos, best)
    lines.append(f"Xem: {title} @ {when} -> {link}" if link else f"Nguồn: {title}")
    if not best["reviewed"]:
        lines.append("(Tri thức chưa được thợ duyệt)")

    others = [cases[i] for i, *_ in case_hits[1:]]
    rel = graph_context(state, best)
    extra = [c for c in others + rel if c["id"] != best["id"]]
    seen = set()
    if extra:
        lines += ["", "Có thể liên quan:"]
        for c in extra:
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            title, when, link = origin(videos, c)
            lines.append(f"  - {c['symptom']} -> {c['cause']}  [{when} {link}]" if link else f"  - {c['symptom']} -> {c['cause']}  [{title}]")
            if len(seen) >= 3:
                break

    lines += ["", "Đoạn trong video:"]
    for i, b, v in chunk_hits[:3]:
        c = chunks[i]
        lines.append(f"  [{mmss(c['start'])}] {c['title']}: {c['text'][:160]}...")
        lines.append(f"     {yt_link(c['video_id'], c['start'])}")
    return "\n".join(lines)

def sql(query):
    db = sqlite3.connect(OUT / "dxa.sqlite")
    cur = db.execute(query)
    cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for row in cur.fetchall():
        print(" | ".join(str(x) for x in row))

if __name__ == "__main__":
    import dxa  # để pickle lưu class dưới tên module "dxa", không phải "__main__"
    build, ask, sql = dxa.build, dxa.ask, dxa.sql
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "ask":
        print(ask(" ".join(sys.argv[2:])))
    elif cmd == "sql":
        sql(" ".join(sys.argv[2:]))
