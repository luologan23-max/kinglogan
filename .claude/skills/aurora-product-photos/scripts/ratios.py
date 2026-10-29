"""量雪茄照片的长宽比，和常见型号的标准比例对照，辅助辨认型号（例如 Siglo I 和半世纪长度一样，粗细不同）。
用法：python3 ratios.py <清点包目录> 164,165,168 [--top 5]
比例 = 长度(mm) ÷ 直径(mm)，直径 = 环径 × 25.4 / 64。照片里的猪尾、阴影会让比例偏大一点，相差 10% 以内都算接近。
只对单支雪茄的侧面横条图有意义；整盒照片不要用。"""
import argparse
import csv
import os
import re

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
# 文件名里的中文品牌 → 表里的英文品牌，用来只和同品牌的型号比
BRAND_CN = {"高希霸": "Cohiba", "蒙特克里斯托": "Montecristo", "蒙特克里斯特": "Montecristo", "帕特加斯": "Partagás",
            "罗密欧": "Romeo y Julieta", "乌普曼": "H. Upmann", "好友": "Hoyo de Monterrey", "特立尼达": "Trinidad",
            "玻利瓦尔": "Bolívar", "潘趣": "Punch", "威古洛": "Vegueros", "多尔塞": "Quai d'Orsay", "胡安": "Juan López",
            "圣克里斯托": "San Cristóbal", "雷蒙": "Ramón Allones", "拉斐尔": "Rafael González"}


def vitolas():
    rows = []
    for line in open(os.path.join(HERE, "..", "references", "vitolas.md"), encoding="utf-8"):
        m = re.match(r"\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", line)
        if m and m.group(2).isdigit():
            name, length, ring = m.group(1), int(m.group(2)), int(m.group(3))
            rows.append((name, length, ring, length / (ring * 25.4 / 64)))
    return rows


def ratio(path):
    im = Image.open(path).convert("L")
    box = im.point(lambda v: 255 if v < 235 else 0).getbbox()  # 非白色区域 = 雪茄
    if not box:
        return None
    w, h = box[2] - box[0], box[3] - box[1]
    return max(w, h) / max(1, min(w, h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("numbers")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--brand", default="", help="只和这个品牌比（英文，例如 Trinidad）；不写就按文件名里的中文品牌自动选")
    a = ap.parse_args()
    man = {int(r["no"]): r for r in csv.DictReader(open(os.path.join(a.inventory, "manifest.csv"), encoding="utf-8-sig"))}
    table = vitolas()
    for n in [int(x) for x in a.numbers.split(",") if x.strip()]:
        r = man[n]
        k = ratio(os.path.join(a.inventory, r["thumb"]))
        if not k:
            print(f"#{n} {r['file']}：量不出")
            continue
        brand = a.brand or next((en for cn, en in BRAND_CN.items() if cn in r["file"]), "")
        pool = [v for v in table if v[0].lower().startswith(brand.lower())] or table
        near = sorted(pool, key=lambda v: abs(v[3] - k))[:a.top]
        print(f"#{n} {r['file']}：长宽比 {k:.2f}  最接近{'（' + brand + '）' if brand and len(pool) < len(table) else ''}：" + "；".join(f"{v[0]} {v[1]}×{v[2]}（{v[3]:.2f}）" for v in near))


if __name__ == "__main__":
    main()
