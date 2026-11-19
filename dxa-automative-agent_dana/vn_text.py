"""Chuẩn hóa câu hỏi mà KHÔNG gọi Gemini khi không cần.

- Tiếng Việt có dấu      -> dùng luôn.
- Tiếng Việt không dấu   -> thêm dấu bằng từ điển rút từ chính phụ đề 30 video và các case
                            (vd "den bao xi nhan" -> "đèn báo xi nhan"). Chạy trên máy, gần 0 giây.
- Tiếng Anh              -> rag.py gọi Gemini dịch sang tiếng Việt một lần, có lưu cache.

Từ điển ghép theo cụm 3 chữ, 2 chữ rồi 1 chữ: cụm dài ít nhầm hơn ("ban dap" -> "bàn đạp",
còn "ban" đứng một mình có thể là bán / bàn / bạn nên chỉ dùng khi một cách viết chiếm đa số).
"""
import re
import unicodedata
from collections import Counter, defaultdict

WORD = re.compile(r"[0-9a-zà-ỹđ]+", re.IGNORECASE)
MAX_N = 3
UNIGRAM_MIN_SHARE = 0.6   # chữ đơn chỉ thêm dấu khi một cách viết chiếm >= 60% số lần xuất hiện


def strip_accents(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def has_accents(s):
    return any(unicodedata.category(ch) == "Mn" for ch in unicodedata.normalize("NFD", s)) or "đ" in s.lower()


class AccentDict:
    def __init__(self, texts):
        self.grams = defaultdict(Counter)   # "den bao" -> Counter({"đèn báo": 12, ...})
        for t in texts:
            words = [w.lower() for w in WORD.findall(unicodedata.normalize("NFC", t or ""))]
            for n in range(1, MAX_N + 1):
                for i in range(len(words) - n + 1):
                    g = " ".join(words[i:i + n])
                    self.grams[strip_accents(g)][g] += 1
        self.vocab = {k for k in self.grams if " " not in k}   # các chữ đơn đã gặp (bỏ dấu)

    def _best(self, key, n):
        c = self.grams.get(key)
        if not c:
            return None
        form, cnt = c.most_common(1)[0]
        if n == 1 and cnt / sum(c.values()) < UNIGRAM_MIN_SHARE:
            return None
        return form

    def restore(self, q):
        """Thêm dấu cho câu gõ không dấu. Chữ không có trong từ điển thì giữ nguyên."""
        words = [w.lower() for w in WORD.findall(q)]
        out, i = [], 0
        while i < len(words):
            for n in range(min(MAX_N, len(words) - i), 0, -1):
                chunk = words[i:i + n]
                if any(has_accents(w) for w in chunk):   # chữ người dùng đã gõ dấu thì giữ
                    continue
                form = self._best(" ".join(chunk), n)
                if form:
                    out.append(form)
                    i += n
                    break
            else:
                out.append(words[i])
                i += 1
        return " ".join(out)

    def vietnamese_share(self, q):
        """Tỉ lệ chữ trong câu là chữ tiếng Việt đã gặp trong video (để đoán câu tiếng Anh)."""
        words = [strip_accents(w.lower()) for w in WORD.findall(q) if not w.isdigit()]
        return sum(w in self.vocab for w in words) / len(words) if words else 1.0


def looks_english(q, accent_dict, min_vi_share=0.5):
    """Câu không dấu mà phần lớn chữ không phải tiếng Việt trong kho -> coi là tiếng Anh."""
    return not has_accents(q) and accent_dict.vietnamese_share(q) < min_vi_share
