"""实拍图按文件名配产品、重复型号判定的测试。python3 tests/photo_match_test.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import aurora_setup as A  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" — {detail}"))
    fails += 0 if ok else 1


def prod(pid, name, sku, status="publish", en=None, cn=None):
    meta = [{"key": "aurora_name_en", "value": en}] if en else []
    return {"id": pid, "name": name, "sku": sku, "status": status, "aurora_name_cn": cn or "", "meta_data": meta}


# 站点原有产品（英文名）+ 标准目录产品（中文名，已改草稿的是重复款）
products = [
    prod(1, "Fonseca No.1", "CUB-133"),
    prod(2, "Montecristo No.2", "CUB-020"),
    prod(3, "Montecristo No.4", "CUB-022"),
    prod(4, "Cohiba Behike BHK 52", "CUB-001"),
    prod(5, "Cohiba Siglo Ill", "CUB-005"),
    prod(6, "Cohiba Siglo VI", "CUB-007"),
    prod(7, "Cohiba Siglo VI", "CUB-008"),  # 站点里本来就有两个同名产品
    prod(8, "La Flor de Cano Preferidos", "CUB-142", cn="卡诺之花 经典"),
    prod(9, "Cohiba Robustos", "CUB-010"),
    prod(10, "Cohiba Robustos Reserva", "CUB-011"),
    prod(11, "Partagas Serie D No.4", "CUB-030"),
    prod(20, "高希霸 贝伊可 52", "COH-BHK52-10", status="draft", en="Cohiba Behike 52"),
    prod(21, "高希霸 世纪六号", "COH-S6-25", status="draft", en="Cohiba Siglo VI"),
    prod(22, "大卫杜夫 签名2号", "DAV-S2-25", en="Davidoff Signature No.2"),
    prod(23, "好友 王子", "HOY-PRI-25", en="Hoyo de Monterrey Le Hoyo du Prince"),
    prod(24, "Hoyo de Monterrey Le Hoyo du Maire", "CUB-060"),
    prod(25, "Punch Punch", "CUB-070"),
    prod(26, "Supremos A", "CUB-080"),
    prod(27, "Supremos B", "CUB-081"),
]
expect = {
    "Fonseca No.1.jpg": ([1], 1),
    "Fonseca No.1 (2).jpg": ([1], 2),
    "Fonseca No.1-3.jpg": ([1], 3),
    "CUB-020.jpg": ([2], 1),                        # 按 SKU
    "montecristo_no_4.JPG": ([3], 1),               # 大小写、下划线
    "Montecristo No.4 2.jpg": ([3], 2),
    "Montecristo No.7.jpg": None,                    # 数字不同，不能配给 No.2 / No.4
    "Cohiba Behike 52.jpg": ([4], 1),                # 上架款优先于完全同名的草稿
    "Cohiba Siglo III.jpg": ([5], 1),                # 产品名把 III 打成了 Ill
    "Cohiba Siglo VI.jpg": ([6, 7], 1),              # 两个同名上架款都配
    "高希霸世纪六号.jpg": ([6], 1),                   # 草稿重复款的中文名指向上架款
    "卡诺之花经典.jpg": ([8], 1),                     # 站点产品的中文名（_name_cn）
    "Cohiba Robustos.jpg": ([9], 1),
    "Partagás Serie D No.4.jpeg": ([11], 1),         # 重音
    "大卫杜夫签名2号.png": ([22], 1),
    "Supremos.jpg": "unsure",                        # 两款同样接近，不能随便配
    "Cohiba.jpg": None,
    "IMG_1234.jpg": None,
}

with tempfile.TemporaryDirectory() as d:
    for name in list(expect) + [".DS_Store", "notes.txt"]:
        open(os.path.join(d, name), "wb").close()
    groups, rows, unmatched, unsure = A.match_photos(d, products)
    got = {}
    for r in rows:
        if r["status"] == "已匹配":
            ids, order = got.get(r["file"], ([], r["order"]))
            got[r["file"]] = (sorted(ids + [r["product_id"]]), order)
    for name, want in expect.items():
        if want is None:
            check(f"未匹配：{name}", name in unmatched, got.get(name))
        elif want == "unsure":
            check(f"不确定：{name}", name in unsure, got.get(name))
        else:
            check(f"{name} → {want}", got.get(name) == want, got.get(name))
    check("非图片文件被忽略", not any(r["file"] in (".DS_Store", "notes.txt") for r in rows))
    check("图集按序号排列", [os.path.basename(f) for f in groups[1]] == ["Fonseca No.1.jpg", "Fonseca No.1 (2).jpg", "Fonseca No.1-3.jpg"],
          groups.get(1))

# 重复型号判定（dedupe 用同一套比对）
same = lambda a, b: A.name_score(A.name_tokens(a), A.name_tokens(b)) >= A.DEDUPE_MIN
check("单复数算同一款", same("Bolívar Royal Coronas", "Bolívar Royal Corona"))
check("多写 BHK 算同一款", same("Cohiba Behike 52", "Cohiba Behike BHK 52"))
check("重复的词只算一次", same("Punch Punch Punch", "Punch Punch"))
check("Siglo Ill = Siglo III", same("Cohiba Siglo III", "Cohiba Siglo Ill"))
check("拼写差异（Connossieur）算同一款", same("H. Upmann Connoisseur No.1", "H.Upmann Connossieur No. 1"))
check("Prince 和 Maire 不是同一款", not same("Hoyo de Monterrey Le Hoyo du Prince", "Hoyo de Monterrey Le Hoyo du Maire"))
check("Genios 和 Magicos 不是同一款", not same("Cohiba Maduro 5 Genios", "Cohiba Maduro 5 Magicos"))
check("No.1 和 No.2 不是同一款", not same("Montecristo No.1", "Montecristo No.2"))
check("Siglo V 和 Siglo VI 不是同一款", not same("Cohiba Siglo V", "Cohiba Siglo VI"))

print("\n全部通过" if not fails else f"\n{fails} 项失败")
sys.exit(1 if fails else 0)
