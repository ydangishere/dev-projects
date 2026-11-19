"""Bộ kiểm thử: câu hỏi kiểu người dùng thật (có câu gõ không dấu) -> case đúng."""
import dxa

QUESTIONS = [
    ("bình xăng con bị chảy xăng hoài, kim xăng bị rỉ", {"C01"}),
    ("xe de lau khong chay bi chay xang", {"C01", "C02", "C04"}),
    ("chỉnh phao xăng sao cho đúng", {"C02", "C03"}),
    ("chạy hay bị hụt xăng mất ga", {"C03"}),
    ("đi bình PE24 mà ga không đều", {"C05"}),
    ("co gió nào đi được bình 24 họng 45", {"C05", "C06"}),
    ("bugi cháy đen canh xăng không được", {"C07"}),
    ("gan bugi dung huong", {"C07"}),
    ("bình xăng con nóng, chạy xa bị giật", {"C08"}),
    ("co xăng bị xì gió", {"C09"}),
    ("móc mắt piston sâu bao nhiêu thì không lủng", {"C10"}),
    ("phân biệt mắt nạp mắt xả trên piston", {"C11"}),
    ("cò mổ bị bó không có độ rơ", {"C14"}),
    ("xe độ chạy một năm bị trễ cam", {"C19"}),
    ("lá khóa bánh cam bị gãy", {"C20"}),
    ("sên cam căng sau khi ráp đầu", {"C12", "C22"}),
    ("đèn trợ sáng chưa bật đã sáng mờ", {"C24"}),
    ("gắn đèn báo xi nhan thì hai bên cùng sáng", {"C25"}),
    ("dau role 4 chan nhu the nao", {"C25"}),
    ("bánh trước bánh sau không ngay hàng", {"C26", "C38"}),
    # --- đợt 2 ---
    ("binh yoshimura keo ga nhanh bi tat may", {"C27"}),
    ("buông ga mà ga không về, bị ngâm ga", {"C28"}),
    ("vệ sinh bình xăng con thế nào, có xịt gió mạnh được không", {"C29"}),
    ("đồng hồ takegawa gắn ngoài chạy nhanh bị sút ra", {"C30"}),
    ("tay ga bị rơ xoay", {"C31"}),
    ("đấu đèn báo xi nhan bóng tóc có cần rơ le không", {"C32", "C25"}),
    ("đi sườn MD xuống đầu CD bị cạ hộp lọc gió", {"C34"}),
    ("bộ số độ không báo số N", {"C37"}),
    ("canh bánh xe bằng đèn laser", {"C38"}),
    ("chén cổ bị rỗ tay lái lỏng", {"C39"}),
    ("côn bị trượt chưa bóp mà đạp đã tuột", {"C40"}),
    ("cần số bị quơ khi ráp máy lỏ trên lốc alpha", {"C41"}),
    ("ráp máy xong quay máy rất cứng", {"C42", "C12", "C22"}),
    ("pha nước tẩy rỉ sét lốc máy", {"C44"}),
    ("dây hàn gió đá bị xì ở đuôi chuột", {"C47"}),
    ("lắp van chống cháy ngược cho bình oxy gas", {"C48"}),
    ("hàn sắt mỏng 1 ly bằng máy hàn điện bị lủng", {"C49"}),
    ("chỉnh lửa đèn cắt oxy gas", {"C50"}),
    ("binh xang con buong ga ma ga khong ve", {"C28"}),   # câu thật gõ không dấu, đang xếp hạng 2
    ("cách đấu đèn báo xi nhan khi không dùng đồng hồ km", {"C32", "C25"}),  # câu thật, từng bị cổng chặn từ chối
]

# Câu gõ không dấu, chạy qua rag.retrieve (thêm dấu bằng từ điển rút từ video, không gọi Gemini)
NO_ACCENT = [
    ("binh xang con chay xang khi dung xe", {"C01", "C02"}),
    ("co mo bi bo khong co do ro", {"C14"}),
    ("con bi truot, chua bop con ma dap da tuot", {"C40"}),
    ("lap den bao xi nhan ma khong can dong ho", {"C32", "C25"}),
    ("moc mat piston sau bao nhieu thi khong lung", {"C10"}),
    ("chay bi hut xang mat ga hoai", {"C03"}),
]

OUT_OF_SCOPE = ["xe đề không nổ", "thay nhớt bao lâu một lần", "phanh đĩa bị kêu", "lốp xe bị xì", "đèn pha không sáng",
                "xe tay ga bị rung đầu", "ắc quy nhanh hết điện", "ô tô bị nóng máy"]

if __name__ == "__main__":
    state = dxa._load()
    h1 = h3 = 0
    for q, gold in QUESTIONS:
        hits, _ = dxa.search(state, q)
        ids = [state["cases"][i]["id"] for i, *_ in hits]
        ok1, ok3 = ids[0] in gold, bool(set(ids[:3]) & gold)
        h1 += ok1; h3 += ok3
        print(f"{'OK ' if ok1 else ('~  ' if ok3 else 'XX ')} {q:55s} -> {ids}  gold={sorted(gold)}")
    n = len(QUESTIONS)
    ok = sum(dxa.scope_level(state, q) == "out" for q in OUT_OF_SCOPE)
    for q in OUT_OF_SCOPE:
        lv = dxa.scope_level(state, q)
        print(f"{'OK ' if lv == 'out' else 'XX '} (ngoài phạm vi) {q}  [{lv}]")
    scope = sum(dxa.in_scope(state, q) for q, _ in QUESTIONS)
    print(f"\nTrả lời được câu trong phạm vi = {scope}/{n}  (cổng chặn không chặn nhầm)")
    print(f"Từ chối đúng câu ngoài phạm vi = {ok}/{len(OUT_OF_SCOPE)}")
    print(f"Hit@1 = {h1}/{n} = {h1/n:.0%}   Hit@3 = {h3}/{n} = {h3/n:.0%}")

    import rag
    na = 0
    for q, gold in NO_ACCENT:
        r = rag.retrieve(q)
        ids = [state["cases"][i]["id"] for i in r["cases"]]
        ok_ = r["in_scope"] and bool(set(ids[:3]) & gold)
        na += ok_
        print(f"{'OK ' if ok_ else 'XX '} (không dấu) {q:45s} -> \"{r['query_used']}\" {ids[:3]}")
    print(f"Câu không dấu trả lời đúng (top 3, không gọi Gemini) = {na}/{len(NO_ACCENT)}")
