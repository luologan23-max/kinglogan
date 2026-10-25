#!/usr/bin/env python3
"""Aurora Cigars 一键配置脚本（只用 Python 标准库）。

用法示例：
  export AURORA_SITE=https://wordpress-1627597-6431471.cloudwaysapps.com
  export AURORA_USER=你的后台登录用户名
  export AURORA_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx'

  python3 aurora_setup.py check                       # 测试连接
  python3 aurora_setup.py configure                   # WooCommerce 设置：USD / 迪拜 / 关闭配送
  python3 aurora_setup.py import aurora_products_full.csv --dry-run   # 先预览字段映射
  python3 aurora_setup.py import aurora_products_full.csv             # 正式导入（按 SKU 去重，可重复跑）
  python3 aurora_setup.py pages                       # 创建首页 / 批发合作 / 配送说明，并设为首页
  python3 aurora_setup.py all aurora_products_full.csv
"""

import argparse
import base64
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# CSV 列名 → 内部字段。列名比较时忽略大小写、空格、下划线和连字符。
FIELD_ALIASES = {
    "sku": ["sku", "code", "编号", "货号", "产品编号"],
    "name_cn": ["name_cn", "namezh", "中文名", "中文名称", "产品名称", "名称", "品名"],
    "name_en": ["name_en", "name", "englishname", "英文名", "英文名称", "productname"],
    "brand": ["brand", "品牌", "brandname"],
    "price": ["price", "price_usd", "usd", "售价", "价格", "零售价", "盒价", "regularprice"],
    "box_count": ["box_count", "boxcount", "count", "qtyperbox", "per_box", "支数", "每盒支数", "包装"],
    "vitola": ["vitola", "型号", "尺寸名称", "雪茄型号", "shape"],
    "length": ["length", "length_mm", "长度", "长度mm"],
    "ring": ["ring", "ring_gauge", "ringgauge", "环径"],
    "strength": ["strength", "浓度", "强度", "口味强度"],
    "wrapper": ["wrapper", "茄衣"],
    "origin": ["origin", "country", "产地", "原产地"],
    "limited": ["limited", "is_limited", "limited_edition", "限量", "限量版", "是否限量"],
    "verify": ["verify", "verified", "防伪", "防伪可查"],
    "stock": ["stock", "stock_qty", "quantity", "库存", "库存数量", "现货"],
    "image": ["image", "images", "image_url", "img", "图片", "图片链接"],
    "description": ["description", "tasting", "notes", "描述", "品鉴", "品鉴描述", "口感描述"],
    "short_description": ["short_description", "summary", "简介", "简述"],
    "category": ["category", "series", "分类", "系列"],
}

META_FIELDS = ["brand", "name_en", "vitola", "length", "ring", "box_count",
               "strength", "wrapper", "origin", "limited", "verify"]

# 首页品牌宫格的顺序（排在前 6 位的就是首屏旗舰品牌）
FLAGSHIP_BRANDS = ["Cohiba", "Montecristo", "Romeo y Julieta", "Partagás",
                   "H. Upmann", "Trinidad", "Hoyo de Monterrey", "Bolívar",
                   "Punch", "Davidoff"]

WC_SETTINGS = {
    "general": {
        "woocommerce_currency": "USD",
        "woocommerce_currency_pos": "left",
        "woocommerce_price_num_decimals": "0",
        "woocommerce_store_address": "Jebel Ali Free Zone (JAFZA)",
        "woocommerce_store_city": "Dubai",
        "woocommerce_default_country": "AE",
        "woocommerce_ship_to_countries": "disabled",
        "woocommerce_calc_taxes": "no",
        "woocommerce_enable_coupons": "no",
    },
    "products": {
        "woocommerce_enable_reviews": "no",
        "woocommerce_enable_ajax_add_to_cart": "no",
        "woocommerce_cart_redirect_after_add": "no",
    },
}


def norm(s):
    return re.sub(r"[\s_\-/()（）]+", "", str(s)).lower()


class WP:
    def __init__(self, site, user, password):
        self.site = site.rstrip("/")
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "aurora-setup/1.0",
        }

    def req(self, method, path, body=None, params=None):
        url = f"{self.site}/wp-json/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(url, data=data, method=method, headers=self.headers)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                raw = resp.read().decode() or "null"
                return json.loads(raw), resp.headers
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:600]
            raise SystemExit(f"✗ {method} {path} → HTTP {e.code}\n{detail}")
        except urllib.error.URLError as e:
            raise SystemExit(f"✗ 连接失败 {url}: {e.reason}")

    def get_all(self, path, params=None):
        params = dict(params or {}, per_page=100, page=1)
        out = []
        while True:
            data, headers = self.req("GET", path, params=params)
            out.extend(data)
            if params["page"] >= int(headers.get("X-WP-TotalPages") or 1):
                return out
            params["page"] += 1


# ---------------------------------------------------------------- 步骤

def cmd_check(wp):
    me, _ = wp.req("GET", "wp/v2/users/me", params={"context": "edit"})
    print(f"✓ 已登录：{me.get('name')}（用户名 {me.get('username')}，角色 {', '.join(me.get('roles', []))}）")
    if "administrator" not in me.get("roles", []) and "shop_manager" not in me.get("roles", []):
        print("! 该账号不是管理员 / 店长，后续写入可能被拒绝")
    status, _ = wp.req("GET", "wc/v3/system_status", params={"_fields": "environment,active_plugins"})
    env = status.get("environment", {})
    print(f"✓ WooCommerce {env.get('version')} · WordPress {env.get('wp_version')}")
    names = sorted(p.get("plugin", "").split("/")[0] for p in status.get("active_plugins", []))
    print("  已启用插件：" + ", ".join(names))
    if "aurora-core" not in names:
        print("! 还没启用 aurora-core 插件 —— 请在后台 插件 → 上传 aurora-core.zip 并启用")


def cmd_configure(wp, dry_run=False):
    for group, values in WC_SETTINGS.items():
        updates = [{"id": k, "value": v} for k, v in values.items()]
        if dry_run:
            print(f"[dry-run] {group}: {values}")
            continue
        res, _ = wp.req("POST", f"wc/v3/settings/{group}/batch", {"update": updates})
        for item in res.get("update", []):
            if "error" in item:
                print(f"! {item.get('id')}: {item['error'].get('message')}")
            else:
                print(f"✓ {item['id']} = {item.get('value')}")


def read_csv(path, overrides):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(f, dialect=dialect))
    if not rows:
        raise SystemExit("✗ CSV 是空的")
    headers = list(rows[0].keys())
    lookup = {norm(h): h for h in headers}
    mapping = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if norm(alias) in lookup and lookup[norm(alias)] not in mapping.values():
                mapping[field] = lookup[norm(alias)]
                break
    for field, column in overrides.items():
        if column not in headers:
            raise SystemExit(f"✗ --map {field}={column}：CSV 中没有这一列。现有列：{headers}")
        mapping[field] = column
    return rows, headers, mapping


def clean_price(value):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(value or ""))
    return m.group(0).replace(",", "") if m else ""


def to_product(row, mapping, cat_ids):
    get = lambda f: (row.get(mapping[f]) or "").strip() if f in mapping else ""
    name = get("name_cn") or get("name_en")
    if not name:
        return None
    product = {
        "name": name,
        "type": "simple",
        "status": "publish",
        "regular_price": clean_price(get("price")),
        "description": get("description"),
        "short_description": get("short_description"),
        "meta_data": [{"key": f"aurora_{f}", "value": get(f)} for f in META_FIELDS if get(f)],
    }
    if get("sku"):
        product["sku"] = get("sku")
    stock = get("stock")
    if stock:
        if re.fullmatch(r"\d+", stock):
            product.update(manage_stock=True, stock_quantity=int(stock))
        else:
            product["stock_status"] = "outofstock" if norm(stock) in ("0", "no", "无", "缺货", "outofstock", "否") else "instock"
    cats = [c for c in (get("brand"), get("category")) if c and c in cat_ids]
    if cats:
        product["categories"] = [{"id": cat_ids[c]} for c in dict.fromkeys(cats)]
    images = [u.strip() for u in re.split(r"[|,\s]+", get("image")) if u.strip().startswith("http")]
    if images:
        product["images"] = [{"src": u} for u in images]
    return product


def ensure_categories(wp, names, dry_run):
    existing = {c["name"]: c["id"] for c in wp.get_all("wc/v3/products/categories", {"_fields": "id,name"})} if not dry_run else {}
    order = {b.lower(): i for i, b in enumerate(FLAGSHIP_BRANDS)}
    for name in sorted(names):
        if name in existing:
            continue
        body = {"name": name, "menu_order": order.get(name.lower(), 100)}
        if dry_run:
            print(f"[dry-run] 新建分类：{name}")
            existing[name] = 0
            continue
        res, _ = wp.req("POST", "wc/v3/products/categories", body)
        existing[name] = res["id"]
        print(f"✓ 新建分类：{name}")
    return existing


def cmd_import(wp, csv_path, overrides, dry_run=False, limit=None):
    rows, headers, mapping = read_csv(csv_path, overrides)
    print(f"读取 {len(rows)} 行，列：{headers}")
    print("字段映射：")
    for field in FIELD_ALIASES:
        print(f"  {field:<18} ← {mapping.get(field, '（未找到，可用 --map 指定）')}")
    if "name_cn" not in mapping and "name_en" not in mapping:
        raise SystemExit("✗ 找不到产品名称列，请用 --map name_cn=列名 指定")
    if limit:
        rows = rows[:limit]

    cat_names = set()
    for row in rows:
        for f in ("brand", "category"):
            if f in mapping and (row.get(mapping[f]) or "").strip():
                cat_names.add(row[mapping[f]].strip())
    cat_ids = ensure_categories(wp, cat_names, dry_run)

    products = [p for p in (to_product(r, mapping, cat_ids) for r in rows) if p]
    print(f"有效产品 {len(products)} 款，跳过 {len(rows) - len(products)} 行（无名称）")
    if dry_run:
        print("[dry-run] 前 2 款转换结果：")
        print(json.dumps(products[:2], ensure_ascii=False, indent=2))
        return

    existing = {p["sku"]: p["id"] for p in wp.get_all("wc/v3/products", {"_fields": "id,sku", "status": "any"}) if p.get("sku")}
    creates, updates = [], []
    for p in products:
        if p.get("sku") in existing:
            p["id"] = existing[p["sku"]]
            p.pop("images", None)  # 已有产品不重复下载图片
            updates.append(p)
        else:
            creates.append(p)
    print(f"新建 {len(creates)} 款，更新 {len(updates)} 款")
    errors = 0
    for i in range(0, max(len(creates), len(updates)), 25):
        body = {"create": creates[i:i + 25], "update": updates[i:i + 25]}
        if not body["create"] and not body["update"]:
            continue
        res, _ = wp.req("POST", "wc/v3/products/batch", body)
        for kind in ("create", "update"):
            for item in res.get(kind, []):
                if item.get("error"):
                    errors += 1
                    print(f"! {kind} 失败：{item['error'].get('message')}")
        print(f"  已处理 {min(i + 25, max(len(creates), len(updates)))} 批次行")
    print(f"✓ 导入完成，失败 {errors} 条")


HOME_HTML = """<!-- wp:html -->
<section class="aurora-hero">
  <p class="aurora-hero__eyebrow">Aurora Cigars · Dubai</p>
  <h1>古巴雪茄，迪拜直供</h1>
  <p>中东授权经销商直供。每一盒都可查防伪，DHL Express 直送到您手中。</p>
  <p>[aurora_whatsapp text="WhatsApp 询价" message="您好，我想了解在售的雪茄。"] &nbsp; <a class="aurora-btn aurora-btn--ghost" href="/shop/">浏览全部雪茄</a></p>
</section>
<section class="aurora-section">
  <h2 class="aurora-section__title">旗舰品牌 · The Houses</h2>
  [aurora_brands limit="6"]
</section>
<section class="aurora-section">
  <div class="aurora-pillars">
    <div><h3>授权直供</h3><p>中东授权经销商渠道，来源清晰可追溯。</p></div>
    <div><h3>防伪可查</h3><p>每盒附原厂防伪标，收货后可自行查验。</p></div>
    <div><h3>全球直发</h3><p>DHL Express，15–20 个工作日送达。</p></div>
  </div>
</section>
<section class="aurora-band">
  <div class="aurora-section">
    <h2 class="aurora-section__title">批发与长期合作</h2>
    <p>雪茄吧、会所与私人藏家，欢迎洽谈批量价格与专属配额。</p>
    <p>[aurora_whatsapp text="洽谈合作" message="您好，我想咨询批发合作。"]</p>
  </div>
</section>
<section class="aurora-section">[aurora_shipping]</section>
<!-- /wp:html -->"""

WHOLESALE_HTML = """<!-- wp:html -->
<section class="aurora-section">
  <h1 class="aurora-section__title">批发合作 · Wholesale</h1>
  <p>Aurora Global Tobacco Trading FZCO 位于迪拜杰贝阿里自贸区（JAFZA），为雪茄吧、会所与藏家提供古巴及非古精品雪茄。</p>
  <p>请通过 WhatsApp 告诉我们您的需求（品牌、数量、目的地），我们会在 24 小时内回复报价与库存。</p>
  <p>[aurora_whatsapp text="WhatsApp 洽谈" message="您好，我想咨询批发合作。"]</p>
</section>
<!-- /wp:html -->"""

SHIPPING_HTML = """<!-- wp:html -->
<section class="aurora-section">
  <h1 class="aurora-section__title">配送与条款 · Shipping</h1>
  [aurora_shipping]
  <p>所有订单通过 WhatsApp 确认，付款方式与发货时间以确认消息为准。</p>
  <p>本网站仅面向年满 21 岁的成年人。</p>
</section>
<!-- /wp:html -->"""

PAGES = [
    ("home", "首页", HOME_HTML),
    ("wholesale", "批发合作", WHOLESALE_HTML),
    ("shipping", "配送与条款", SHIPPING_HTML),
]


def cmd_pages(wp, dry_run=False):
    ids = {}
    for slug, title, html in PAGES:
        if dry_run:
            print(f"[dry-run] 页面 /{slug}/ {title}")
            continue
        found, _ = wp.req("GET", "wp/v2/pages", params={"slug": slug, "status": "publish,draft", "_fields": "id"})
        body = {"title": title, "slug": slug, "content": html, "status": "publish"}
        if found:
            res, _ = wp.req("POST", f"wp/v2/pages/{found[0]['id']}", body)
            print(f"✓ 更新页面 /{slug}/")
        else:
            res, _ = wp.req("POST", "wp/v2/pages", body)
            print(f"✓ 新建页面 /{slug}/")
        ids[slug] = res["id"]
    if not dry_run:
        wp.req("POST", "wp/v2/settings", {"show_on_front": "page", "page_on_front": ids["home"],
                                          "title": "Aurora Cigars", "description": "古巴雪茄 · 迪拜直供"})
        print("✓ 已设为网站首页")


def main():
    ap = argparse.ArgumentParser(description="Aurora Cigars WooCommerce 配置与导入")
    ap.add_argument("command", choices=["check", "configure", "import", "pages", "all"])
    ap.add_argument("csv", nargs="?", help="产品 CSV 文件（import / all 需要）")
    ap.add_argument("--map", action="append", default=[], metavar="字段=列名",
                    help="手动指定字段映射，例如 --map price=USD售价")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写入网站")
    ap.add_argument("--limit", type=int, help="只导入前 N 行（测试用）")
    args = ap.parse_args()

    overrides = {}
    for m in args.map:
        field, _, column = m.partition("=")
        if field not in FIELD_ALIASES or not column:
            raise SystemExit(f"✗ --map 格式应为 字段=列名，字段可选：{list(FIELD_ALIASES)}")
        overrides[field] = column

    if args.command in ("import", "all") and not args.csv:
        raise SystemExit("✗ 请提供产品 CSV 路径")

    site = os.environ.get("AURORA_SITE", "https://wordpress-1627597-6431471.cloudwaysapps.com")
    user = os.environ.get("AURORA_USER")
    password = os.environ.get("AURORA_APP_PASSWORD")
    if not (user and password) and not (args.dry_run and args.command == "import"):
        raise SystemExit("✗ 请先设置环境变量 AURORA_USER 和 AURORA_APP_PASSWORD")
    wp = WP(site, user or "", password or "")

    if args.command in ("check", "all"):
        cmd_check(wp)
    if args.command in ("configure", "all"):
        cmd_configure(wp, args.dry_run)
    if args.command in ("import", "all"):
        cmd_import(wp, args.csv, overrides, args.dry_run, args.limit)
    if args.command in ("pages", "all"):
        cmd_pages(wp, args.dry_run)


if __name__ == "__main__":
    main()
