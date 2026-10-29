"""照片对照审查页：每张照片和配到的产品并排显示，按「推断 / 待确认 / 直接对应 / 新建草稿 / 不上传」分组。
用法：python3 review_page.py <photo-mapping.csv> <清点包目录> <输出 html> [--source "访达文件夹「1211」"]
生成的是单个 HTML 文件（缩略图内嵌），用 Artifact 发布给用户核对；同一个文件路径重新发布会更新同一个链接。"""
import argparse
import base64
import csv
import html
import io
import os

from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("mapping")
ap.add_argument("inventory")
ap.add_argument("out")
ap.add_argument("--source", default="")
args = ap.parse_args()
mapping, thumbs_base, out = args.mapping, args.inventory, args.out
man = {int(r["no"]): r for r in csv.DictReader(open(os.path.join(thumbs_base, "manifest.csv"), encoding="utf-8-sig"))}
rows = list(csv.DictReader(open(mapping, encoding="utf-8-sig")))

def thumb(no):
    im = Image.open(f"{thumbs_base}/{man[no]['thumb']}").convert("RGB")
    im.thumbnail((640, 220))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), im.size

def kind(r):
    if r["status"] == "确认":
        return "new" if r["sku"].startswith("LTD-") else "guess" if r["note"].startswith("推断") else "ok"
    return "hold" if r["status"] == "待确认" else "skip"

groups = {"guess": [], "hold": [], "ok": [], "new": [], "skip": []}
for r in rows:
    groups[kind(r)].append(r)
meta = {
    "guess": ("推断配图", "已上传，请核对", "文件名和产品名不完全一样，按品牌、环标和雪茄长宽比例推断的。配错了告诉我编号就改。"),
    "hold": ("待确认", "未上传", "有候选产品但拿不准，或认不出型号。确认后告诉我，下次运行就上传。"),
    "ok": ("直接对应", "已上传", "文件名、环标和站上的产品名一一对应。"),
    "new": ("新建草稿", "草稿 · 不对外", "网站上原来没有的地区限量、特别版和保湿盒，建成草稿并配上照片，名称用文件名原文、标红。英文官方名、价格、规格补好后再发布。"),
    "skip": ("不上传", "不上传", "和另一张照片内容完全相同，或者站上没有对应产品、也不新建。"),
}
products = len({r["sku"] for r in rows if r["status"] == "确认" and not r["sku"].startswith("LTD-")})
photos = sum(1 for r in rows if r["status"] == "确认" and not r["sku"].startswith("LTD-"))
new_products = len({r["sku"] for r in rows if r["sku"].startswith("LTD-")})
new_photos = sum(1 for r in rows if r["sku"].startswith("LTD-"))

def item(r):
    no = int(r["no"])
    src, (w, h) = thumb(no)
    tall = h > w
    target = (f'<span class="sku">{html.escape(r["sku"])}</span><span class="pname">{html.escape(r["product"])}</span>'
              if r["sku"] else '<span class="pname none">没有对应的产品</span>')
    role = (f'<span class="role">{ {"包装": "图集 · 整盒照", "其他": "图集 · 第二张"}.get(r["role"], "主图") }</span>'
            if r["status"] == "确认" else "")
    return f'''<li class="row {kind(r)}" id="p{no}">
  <figure class="ph{' tall' if tall else ''}"><img src="{src}" width="{w}" height="{h}" alt="{html.escape(r['file'])}" loading="lazy"></figure>
  <div class="info">
    <p class="file"><span class="no">#{no}</span>{html.escape(r["file"])}</p>
    <p class="target">{target}{role}</p>
    <p class="note">{html.escape(r["note"])}</p>
  </div>
</li>'''

sections = []
for key in ("guess", "hold", "ok", "new", "skip"):
    name, state, desc = meta[key]
    items = "\n".join(item(r) for r in groups[key])
    sections.append(f'''<section class="grp {key}" id="{key}">
  <header class="gh"><h2>{name}<span class="count">{len(groups[key])} 张</span></h2><span class="pill {key}">{state}</span></header>
  <p class="gdesc">{desc}</p>
  <ol class="rows">{items}</ol>
</section>''')

chips = "".join(f'<a class="chip {k}" href="#{k}"><b>{len(groups[k])}</b>{meta[k][0]}</a>' for k in ("guess", "hold", "ok", "new", "skip"))
page = f'''<title>Aurora 雪茄配图对照</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700&family=Noto+Sans+SC:wght@400;500;700&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* 一列清单：每行左边是照片，右边是配到的产品；四组按需要核对的程度排序 */
:root {{
  --mat: #FFFFFF; --bg: #F6F6F3; --surface: #FFFFFF; --fg: #1D1A17; --muted: #6C655E; --line: #E2DED8;
  --accent: #7A4426;
  --ok: #2E7A4C; --ok-bg: #E5F2EA; --guess: #A86412; --guess-bg: #FBEEDB; --hold: #2C64A8; --hold-bg: #E3ECF8; --skip: #7A746D; --skip-bg: #ECEAE6; --new: #8A3B5C; --new-bg: #F5E4EC;
  --serif: "Noto Serif SC", "Songti SC", "STSong", serif;
  --sans: "Noto Sans SC", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #161412; --surface: #201D1A; --fg: #EDE8E2; --muted: #A39B92; --line: #36312C; --accent: #D9976C;
  --ok: #6CC793; --ok-bg: #1D3326; --guess: #F0B061; --guess-bg: #3A2A14; --hold: #82B1F0; --hold-bg: #1B2A40; --skip: #A39B92; --skip-bg: #2A2622; --new: #E59BBB; --new-bg: #3A1F2B;
  color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #161412; --surface: #201D1A; --fg: #EDE8E2; --muted: #A39B92; --line: #36312C; --accent: #D9976C;
  --ok: #6CC793; --ok-bg: #1D3326; --guess: #F0B061; --guess-bg: #3A2A14; --hold: #82B1F0; --hold-bg: #1B2A40; --skip: #A39B92; --skip-bg: #2A2622; --new: #E59BBB; --new-bg: #3A1F2B;
  color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--fg); font: 15px/1.6 var(--sans); }}
.wrap {{ max-width: 1040px; margin: 0 auto; padding-block: 40px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
.top {{ display: grid; gap: 12px; margin-bottom: 28px; }}
.eyebrow {{ font: 500 12px/1 var(--sans); letter-spacing: .14em; color: var(--accent); margin: 0; }}
h1 {{ font: 700 clamp(26px, 4vw, 34px)/1.25 var(--serif); margin: 0; text-wrap: balance; }}
.lede {{ margin: 0; color: var(--muted); max-width: 62ch; }}
.lede b {{ color: var(--fg); font-weight: 500; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
.chip {{ display: inline-flex; align-items: baseline; gap: 6px; padding: 7px 14px; border-radius: 999px; text-decoration: none;
  font-size: 14px; border: 1px solid transparent; }}
.chip b {{ font: 500 15px var(--mono); font-variant-numeric: tabular-nums; }}
.chip:focus-visible, .chip:hover {{ border-color: currentColor; }}
.chip.ok, .pill.ok {{ background: var(--ok-bg); color: var(--ok); }}
.chip.guess, .pill.guess {{ background: var(--guess-bg); color: var(--guess); }}
.chip.hold, .pill.hold {{ background: var(--hold-bg); color: var(--hold); }}
.chip.new, .pill.new {{ background: var(--new-bg); color: var(--new); }}
.chip.skip, .pill.skip {{ background: var(--skip-bg); color: var(--skip); }}
.grp {{ margin-top: 40px; scroll-margin-top: 16px; }}
.gh {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  border-bottom: 1px solid var(--line); padding-bottom: 10px; }}
h2 {{ font: 700 21px/1.3 var(--serif); margin: 0; display: flex; align-items: baseline; gap: 10px; }}
.count {{ font: 500 14px var(--mono); color: var(--muted); }}
.pill {{ font-size: 12px; padding: 3px 10px; border-radius: 999px; letter-spacing: .04em; }}
.gdesc {{ color: var(--muted); margin: 10px 0 4px; max-width: 70ch; font-size: 14px; }}
.rows {{ list-style: none; margin: 0; padding: 0; }}
.row {{ display: grid; grid-template-columns: minmax(0, 340px) minmax(0, 1fr); gap: 20px; align-items: center;
  padding: 16px 0; border-bottom: 1px solid var(--line); }}
.ph {{ margin: 0; background: var(--mat); border: 1px solid var(--line); border-radius: 6px; padding: 10px;
  display: flex; align-items: center; justify-content: center; min-height: 84px; }}
.ph img {{ display: block; width: 100%; height: auto; }}
.ph.tall img {{ width: auto; max-height: 180px; }}
.info {{ min-width: 0; display: grid; gap: 4px; }}
.info p {{ margin: 0; overflow-wrap: anywhere; }}
.file {{ font-size: 13px; color: var(--muted); }}
.no {{ font: 500 12px var(--mono); color: var(--accent); margin-right: 8px; }}
.target {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }}
.sku {{ font: 500 13px var(--mono); padding: 1px 7px; border-radius: 4px; background: var(--skip-bg); color: var(--fg); }}
.pname {{ font-weight: 500; font-size: 16px; }}
.pname.none {{ color: var(--muted); font-weight: 400; font-size: 14px; }}
.role {{ font-size: 12px; color: var(--muted); }}
.note {{ font-size: 13.5px; color: var(--muted); }}
.row.guess .note, .row.hold .note {{ color: var(--fg); }}
.skip .row {{ padding: 10px 0; }}
.skip .ph {{ min-height: 0; padding: 6px; }}
.skip .note {{ display: none; }}
.foot {{ margin-top: 48px; color: var(--muted); font-size: 13px; max-width: 70ch; }}
@media (max-width: 640px) {{
  .row {{ grid-template-columns: minmax(0, 1fr); gap: 10px; }}
}}
</style>
<div class="wrap">
  <header class="top">
    <p class="eyebrow">AURORA CIGARS{(' · ' + html.escape(args.source)) if args.source else ''} · {len(rows)} 张</p>
    <h1>雪茄照片与产品对照</h1>
    <p class="lede">每张照片都看过图、对过文件名和环标。<b>{photos} 张照片配给站上已有的 {products} 款产品</b>（3 张整盒照放进图集）；站上没有的 {new_products} 款限量 / 特别版新建为草稿，配上 {new_photos} 张照片。横条图上传时放到白底正方形里，商品卡上能看到整支雪茄；原图不改动。</p>
    <nav class="chips" aria-label="分组">{chips}</nav>
  </header>
  {"".join(sections)}
  <p class="foot">配错或想改：告诉我照片编号（例如 #137）和正确的产品即可。没列在这里的照片还没有清点。</p>
</div>
'''
open(out, "w", encoding="utf-8").write(page)
print(f"{out}（{len(page) // 1024} KB）")
