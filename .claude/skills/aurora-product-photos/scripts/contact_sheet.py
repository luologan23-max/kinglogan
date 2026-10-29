"""把清点包里的缩略图拼成带编号和文件名的对照图，方便逐张看图核对。
用法：python3 contact_sheet.py <解压后的清点包目录> <输出目录> [--only 12,40,137] [--per 20] [--width 700]
- 看的是「原始像素」（不按 EXIF 方向旋转）：上传时会去掉 EXIF，网站显示的就是这个样子。
- 输出 sheet01.jpg、sheet02.jpg……；--only 只拼指定编号（放大看细节时用，宽 1000px）。"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for path in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/System/Library/Fonts/PingFang.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--per", type=int, default=20)
    ap.add_argument("--width", type=int, default=700)
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(os.path.join(a.inventory, "manifest.csv"), encoding="utf-8-sig")) if r["thumb"]]
    if a.only:
        keep = {int(x) for x in a.only.split(",") if x.strip()}
        rows = [r for r in rows if int(r["no"]) in keep]
        a.width, a.per = 1000, len(rows) or 1
    os.makedirs(a.out, exist_ok=True)
    f, label_h, max_h = font(20 if a.width < 900 else 22), 30, 110 if a.width < 900 else 400
    for start in range(0, len(rows), a.per):
        chunk, tiles = rows[start:start + a.per], []
        for r in chunk:
            im = Image.open(os.path.join(a.inventory, r["thumb"])).convert("RGB")
            im.thumbnail((a.width, max_h))
            tiles.append((r, im))
        sheet = Image.new("RGB", (a.width, sum(im.height + label_h + 6 for _, im in tiles)), "white")
        d, y = ImageDraw.Draw(sheet), 0
        for r, im in tiles:
            folder = f"{r['folder']}/" if r.get("folder") else ""
            d.text((4, y + 3), f"#{r['no']} {folder}{r['file']}  ({r['width']}×{r['height']})", fill="black", font=f)
            sheet.paste(im, (0, y + label_h))
            y += im.height + label_h + 6
            d.line((0, y - 3, a.width, y - 3), fill="#cccccc")
        name = "zoom.jpg" if a.only else f"sheet{start // a.per + 1:02d}.jpg"
        sheet.save(os.path.join(a.out, name), quality=82)
        print(os.path.join(a.out, name))


if __name__ == "__main__":
    main()
