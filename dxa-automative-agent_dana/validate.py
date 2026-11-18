"""
Kiểm tra tự động từng bước của pipeline. Chạy sau mỗi lần nạp thêm video:
    python dxa.py build && python validate.py

Bước 1  Lấy phụ đề    : đủ chữ so với thời lượng không (video chỉ có hình / lấy thiếu)
Bước 2  Làm sạch       : còn lỗi nghe sai không, mốc giây có hợp lệ không
Bước 3  Rút tri thức   : có BỊA không (con số, từ khóa phải có trong phụ đề quanh giây t)
Bước 4  Graph + SQL    : thiếu liên kết, đếm lệch
"""
import re, sqlite3, sys
import dxa

DATA, OUT = dxa.DATA, dxa.OUT
results = []

def report(step, level, msg):
    results.append((step, level, msg))

def secs(d):
    m, s = d.split(":")
    return int(m) * 60 + int(s)

videos = dxa.load_videos()
chunks = dxa.load_chunks(videos)
cases = dxa.load_cases()
by_vid = {}
for c in chunks:
    by_vid.setdefault(c["video_id"], []).append(c)

# ------------------------------------------------------------------ Bước 1
raw = {}
p = DATA / "raw_stats.tsv"
if p.exists():
    for line in p.read_text(encoding="utf-8").splitlines()[1:]:
        vid, words, last = line.split("\t")
        raw[vid] = (int(words), int(last))
for vid, v in videos.items():
    dur = secs(v["duration"])
    has_text = vid in by_vid
    if v["status"].startswith("bo_qua"):
        if has_text:
            report(1, "WARN", f"{vid}: đánh dấu bỏ qua nhưng vẫn có file clean")
        continue
    if not has_text:
        report(1, "FAIL", f"{vid}: status={v['status']} mà không có file clean")
        continue
    if vid in raw:
        words, last = raw[vid]
        wpm = words / (dur / 60)
        if wpm < 60:
            report(1, "WARN", f"{vid}: chỉ {wpm:.0f} chữ/phút, video nhiều đoạn chỉ có hình")
        if last < dur * 0.8:
            report(1, "WARN", f"{vid}: phụ đề dừng ở {last}s / {dur}s, có thể bị cắt")

# ------------------------------------------------------------------ Bước 2
ASR_ERRORS = ["takawa", "takwa", "yimura", "yosimura", "kehin", "xú bắp", "s bắp", "buri ", "ranti", "rang ti"]
for vid, cs in by_vid.items():
    text = " ".join(c["text"].lower() for c in cs)
    for e in ASR_ERRORS:
        if e in text:
            report(2, "FAIL", f"{vid}: còn lỗi nghe sai '{e.strip()}'")
    starts = [c["start"] for c in cs]
    if starts != sorted(starts):
        report(2, "FAIL", f"{vid}: mốc giây không tăng dần")
    dur = secs(videos[vid]["duration"])
    if starts and starts[-1] > dur:
        report(2, "FAIL", f"{vid}: mốc {starts[-1]}s vượt thời lượng {dur}s")
    for c in cs:
        n = len(c["text"].split())
        if n < 8:
            report(2, "WARN", f"{c['chunk_id']}: đoạn quá ngắn ({n} chữ)")
        if n > 250:
            report(2, "WARN", f"{c['chunk_id']}: đoạn quá dài ({n} chữ), nên chia nhỏ")

# ------------------------------------------------------------------ Bước 3
REQUIRED = ["id", "video_id", "t", "system", "symptom", "cause", "fix", "parts", "tools", "vehicles", "specs", "warnings", "reviewed"]
STOP = set("của là và có thì cho các những một được không khi để với bị ra vào lên xuống này đó nó mình anh em cũng phải rồi theo hoặc".split())
ids = [c.get("id") for c in cases]
for dup in {i for i in ids if ids.count(i) > 1}:
    report(3, "FAIL", f"trùng id case {dup}")

def bigrams(s):
    w = re.findall(r"[0-9a-zà-ỹđ]+", s.lower())
    return {a + " " + b for a, b in zip(w, w[1:]) if not (a in STOP and b in STOP)}

def words(s):
    return {w for w in re.findall(r"[0-9a-zà-ỹđ]+", s.lower()) if w not in STOP and len(w) > 1}

for c in cases:
    miss = [k for k in REQUIRED if k not in c]
    if miss:
        report(3, "FAIL", f"{c.get('id')}: thiếu trường {miss}")
        continue
    if c.get("source") == "tho":
        # case thợ nhập trên tab Bổ sung kiến thức: không có video để đối chiếu, nguồn là chính người thợ
        if not re.fullmatch(r"T\d+", c["id"]):
            report(3, "FAIL", f"{c['id']}: case thợ nhập phải có mã dạng Txx")
        if not c.get("author") or not c.get("created_at"):
            report(3, "FAIL", f"{c['id']}: case thợ nhập thiếu người nhập hoặc ngày nhập")
        continue
    vid = c["video_id"]
    if vid not in by_vid:
        report(3, "FAIL", f"{c['id']}: video {vid} không có transcript")
        continue
    dur = secs(videos[vid]["duration"])
    if not 0 <= c["t"] <= dur:
        report(3, "FAIL", f"{c['id']}: t={c['t']} nằm ngoài video ({dur}s)")
    full = " ".join(x["text"] for x in by_vid[vid]).lower()
    # (a) mọi con số trong thông số phải xuất hiện trong phụ đề
    for s in c["specs"]:
        for num in re.findall(r"\d+(?:\.\d+)?", s["value"]):
            alt = {num, num.replace(".", ","), num.rstrip("0").rstrip(".")}
            if num.startswith("0.") and s["unit"] == "mm":
                alt.add(str(round(float(num) * 10)))  # 1 dem = 0.1 mm
            if not any(re.search(r"(?<![\d.])" + re.escape(a) + r"(?![\d])", full) for a in alt):
                report(3, "FAIL", f"{c['id']}: con số '{num}' ({s['name']}) không có trong phụ đề -> có thể bị bịa")
    # (b) cụm 2 chữ của triệu chứng + cách sửa phải có trong phụ đề quanh giây t (±180s)
    #     Ngưỡng đo trên 53 case thật: thấp nhất 0.18; case bịa thử nghiệm: 0.00
    near = " ".join(x["text"] for x in by_vid[vid] if abs(x["start"] - c["t"]) <= 180)
    kw = bigrams(c["symptom"] + " " + c["fix"])
    cover = len(kw & bigrams(near)) / max(1, len(kw))
    if cover < 0.10:
        report(3, "FAIL", f"{c['id']}: chỉ {cover:.0%} cụm từ có trong phụ đề quanh {c['t']}s -> có thể bị bịa hoặc sai t")
    elif cover < 0.15:
        report(3, "WARN", f"{c['id']}: chỉ {cover:.0%} cụm từ có trong phụ đề quanh {c['t']}s -> nên xem lại")
    # (c) phụ tùng phải được nhắc trong video
    for part in c["parts"]:
        if not words(part) & words(full):
            report(3, "WARN", f"{c['id']}: phụ tùng '{part}' không thấy trong phụ đề")

# ------------------------------------------------------------------ Bước 4
import pickle, networkx as nx
state = pickle.load(open(OUT / "state.pkl", "rb"))  # noqa: S301 - file do DXA tự tạo
G = state["graph"]
for n, d in G.nodes(data=True):
    if d["kind"] == "TrieuChung" and not any(e[2]["rel"] == "DO" for e in G.out_edges(n, data=True)):
        report(4, "FAIL", f"triệu chứng không có nguyên nhân: {d['name'][:50]}")
    if d["kind"] == "NguyenNhan" and not any(e[2]["rel"] == "SUA_BANG" for e in G.out_edges(n, data=True)):
        report(4, "FAIL", f"nguyên nhân không có cách sửa: {d['name'][:50]}")
for u, v, d in G.edges(data=True):
    if not d.get("video_id") and d.get("source") != "tho":
        report(4, "FAIL", f"cạnh {u}->{v} không có video nguồn")
db = sqlite3.connect(OUT / "dxa.sqlite")
for table, expect in [("cases", len(cases)), ("chunks", len(chunks)),
                      ("parts", sum(len(c["parts"]) for c in cases)), ("specs", sum(len(c["specs"]) for c in cases))]:
    got = db.execute(f"select count(*) from {table}").fetchone()[0]  # noqa: S608 - tên bảng lấy từ danh sách cố định
    if got != expect:
        report(4, "FAIL", f"bảng {table}: SQL có {got} dòng, JSON có {expect}")
orphan = db.execute("select count(*) from cases where video_id is not null and video_id not in (select video_id from videos)").fetchone()[0]
if orphan:
    report(4, "FAIL", f"{orphan} case trỏ tới video không tồn tại")

# ------------------------------------------------------------------ in kết quả
names = {1: "Lấy phụ đề", 2: "Làm sạch", 3: "Rút tri thức", 4: "Graph + SQL"}
fails = 0
for step in range(1, 5):
    rs = [r for r in results if r[0] == step]
    f = sum(r[1] == "FAIL" for r in rs); w = sum(r[1] == "WARN" for r in rs)
    fails += f
    print(f"Bước {step} {names[step]:13s}: {'PASS' if not rs else ''}{f' {f} FAIL' if f else ''}{f' {w} WARN' if w else ''}")
    for _, lvl, msg in rs:
        print(f"    {lvl}  {msg}")
print(f"\nVideo: {len(videos)} | có nội dung: {len(by_vid)} | đoạn: {len(chunks)} | case: {len(cases)}")
sys.exit(1 if fails else 0)
