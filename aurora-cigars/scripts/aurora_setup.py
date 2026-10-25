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
  python3 aurora_setup.py pages                       # 创建首页、关于、防伪查验、FAQ、批发、条款页面，并设为首页
  python3 aurora_setup.py images                      # 给没有图片的产品配品牌图，并设置品牌分类封面
  python3 aurora_setup.py images --photos ~/实拍图     # 按 SKU 命名的实拍图替换（COH-ROB-25.jpg、COH-ROB-25-2.jpg…）
  python3 aurora_setup.py images --urls temp.csv      # 临时网图（sku,url），仅供内部预览
  python3 aurora_setup.py images --clear-temp         # 临时图全部换回品牌图
  python3 aurora_setup.py menu                        # 创建主导航
  python3 aurora_setup.py cleanup                     # 停用 YITH / Click to Chat / PayPal（不在 all 里）
  python3 aurora_setup.py all aurora_products_full.csv
"""

import argparse
import base64
import csv
import json
import os
import re
import sys
import unicodedata
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

CONTENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "content")

# 品牌介绍；文件中的顺序就是首页品牌宫格的顺序（前 6 个是首屏旗舰品牌）
with open(os.path.join(CONTENT_DIR, "brands.json"), encoding="utf-8") as _f:
    BRANDS = json.load(_f)

# (slug, 标题, 内容文件)
PAGES = [
    ("home", "首页", "home.html"),
    ("about", "关于我们", "about.html"),
    ("verify", "防伪查验", "verify.html"),
    ("faq", "常见问题", "faq.html"),
    ("wholesale", "批发合作", "wholesale.html"),
    ("shipping", "配送与条款", "shipping.html"),
]

# 主导航：(标题, 路径)
MENU = [
    ("雪茄 Cigars", "/shop/"),
    ("品牌 Houses", "/#brands"),
    ("防伪查验", "/verify/"),
    ("批发合作", "/wholesale/"),
    ("关于我们", "/about/"),
    ("常见问题", "/faq/"),
]

# cleanup 命令会停用的插件（功能已由 aurora-core 提供，或询价模式用不到）
REDUNDANT_PLUGINS = ["yith-woocommerce-wishlist", "click-to-chat-for-whatsapp",
                     "woocommerce-paypal-payments"]

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


def brand_key(s):
    """品牌比对用：去掉重音、标点和大小写，Partagás = partagas = PARTAGAS。"""
    s = unicodedata.normalize("NFKD", str(s))
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def find_brand(name):
    key = brand_key(name)
    for i, b in enumerate(BRANDS):
        if key in (brand_key(b["name"]), brand_key(b["name_cn"]), brand_key(b["slug"])):
            return i, b
    return None, None


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

    def req(self, method, path, body=None, params=None, raw=None, extra_headers=None):
        url = f"{self.site}/wp-json/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        r = urllib.request.Request(url, data=data, method=method, headers=dict(self.headers, **(extra_headers or {})))
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                raw = resp.read().decode() or "null"
                return json.loads(raw), resp.headers
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:600]
            raise SystemExit(f"✗ {method} {path} → HTTP {e.code}\n{detail}")
        except urllib.error.URLError as e:
            raise SystemExit(f"✗ 连接失败 {url}: {e.reason}")

    def upload(self, file_path, filename, alt):
        with open(file_path, "rb") as f:
            raw = f.read()
        ctype = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        media, _ = self.req("POST", "wp/v2/media", raw=raw, extra_headers={
            "Content-Type": ctype,
            "Content-Disposition": f'attachment; filename="{filename}"',
        })
        self.req("POST", f"wp/v2/media/{media['id']}", {"alt_text": alt, "title": alt})
        return media["id"]

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
    """按名称建分类；能对上 brands.json 的品牌，会顺带写入介绍和排序。"""
    cats = wp.get_all("wc/v3/products/categories", {"_fields": "id,name,description"}) if not dry_run else []
    existing = {c["name"]: c for c in cats}
    ids = {}
    for name in sorted(names):
        order, brand = find_brand(name)
        info = {"menu_order": 100 if order is None else order}
        if brand:
            info["description"] = brand["description"]
        cat = existing.get(name)
        if cat:
            ids[name] = cat["id"]
            if brand and not cat.get("description") and not dry_run:
                wp.req("POST", f"wc/v3/products/categories/{cat['id']}", info)
                print(f"✓ 补充品牌介绍：{name}")
            continue
        if dry_run:
            print(f"[dry-run] 新建分类：{name}" + ("（含品牌介绍）" if brand else ""))
            ids[name] = 0
            continue
        res, _ = wp.req("POST", "wc/v3/products/categories", dict(info, name=name))
        ids[name] = res["id"]
        print(f"✓ 新建分类：{name}" + ("（含品牌介绍）" if brand else ""))
    return ids


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


def cmd_pages(wp, dry_run=False):
    ids = {}
    for slug, title, filename in PAGES:
        with open(os.path.join(CONTENT_DIR, "pages", filename), encoding="utf-8") as f:
            html = f.read()
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


IMAGE_DIR = os.path.join(CONTENT_DIR, "images")
PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp")


def brand_media(wp, dry_run):
    """上传 content/images 里的品牌图（已上传过的按文件名复用），返回 {slug: media_id}。"""
    have = {}
    if not dry_run:
        for m in wp.get_all("wp/v2/media", {"search": "aurora-brand-", "_fields": "id,slug"}):
            have[m["slug"]] = m["id"]
    ids = {}
    for b in BRANDS + [{"slug": "aurora", "name": "Aurora Cigars"}]:
        path = os.path.join(IMAGE_DIR, b["slug"] + ".jpg")
        if not os.path.exists(path):
            continue
        key = f"aurora-brand-{b['slug']}"
        if key in have:
            ids[b["slug"]] = have[key]
        elif dry_run:
            print(f"[dry-run] 上传品牌图 {key}.jpg")
            ids[b["slug"]] = 0
        else:
            ids[b["slug"]] = wp.upload(path, key + ".jpg", f"{b['name']} 雪茄")
            print(f"✓ 上传品牌图 {key}.jpg")
    return ids


def sku_photos(photo_dir, skus):
    """实拍图按 SKU 命名：COH-ROB-25.jpg 为主图，COH-ROB-25-2.jpg、-3… 为图集（不区分大小写）。
    先整名匹配 SKU，再尝试去掉末尾的「-序号」，所以 SKU 本身以数字结尾也不会认错。"""
    groups, unmatched = {}, []
    if not photo_dir:
        return groups, unmatched
    for name in sorted(os.listdir(photo_dir)):
        stem, ext = os.path.splitext(name)
        if ext.lower() not in PHOTO_EXT:
            continue
        key, order = stem.upper(), 1
        if key not in skus:
            base, _, num = key.rpartition("-")
            if base in skus and num.isdigit():
                key, order = base, int(num)
            else:
                unmatched.append(name)
                continue
        groups.setdefault(key, []).append((order, os.path.join(photo_dir, name)))
    return {k: [p for _, p in sorted(v)] for k, v in groups.items()}, unmatched


def read_image_urls(path):
    """临时图清单 CSV：两列 sku,url（有表头）。返回 {SKU: [url, …]}，同一 SKU 多行即图集。"""
    urls = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            row = {norm(k): (v or "").strip() for k, v in row.items()}
            sku, url = row.get("sku", "").upper(), row.get("url", "")
            if sku and url.startswith("http"):
                urls.setdefault(sku, []).append(url)
    return urls


def image_source(p):
    return next((m["value"] for m in p.get("meta_data", []) if m["key"] == "aurora_image_source"), "")


def cmd_images(wp, photo_dir=None, url_csv=None, clear_temp=False, dry_run=False):
    """图片来源优先级：实拍图（photo）> 临时网图（temp）> 品牌渲染图（brand）。
    每款产品记录 aurora_image_source，便于之后整批替换临时图。"""
    if photo_dir and not os.path.isdir(photo_dir):
        raise SystemExit(f"✗ 找不到图片目录：{photo_dir}")
    brand_ids = brand_media(wp, dry_run)
    products = wp.get_all("wc/v3/products", {"_fields": "id,sku,name,images,categories,meta_data", "status": "any"})
    skus = {(p.get("sku") or "").upper() for p in products if p.get("sku")}
    photos, unmatched = sku_photos(photo_dir, skus)
    if photo_dir:
        print(f"实拍图目录：匹配 {len(photos)} 个 SKU")
        for name in unmatched:
            print(f"! 未匹配任何 SKU，跳过：{name}")
    web = read_image_urls(url_csv) if url_csv else {}
    if url_csv:
        print(f"临时图清单：{len(web)} 个 SKU" + "".join(f"\n! 清单里的 SKU 不存在：{k}" for k in web if k not in skus))
    if dry_run:
        for sku, files in photos.items():
            print(f"[dry-run] 实拍 {sku} ← {', '.join(os.path.basename(f) for f in files)}")
        for sku, links in web.items():
            print(f"[dry-run] 临时 {sku} ← {links[0]}" + (f" 等 {len(links)} 张" if len(links) > 1 else ""))
        return

    # 品牌分类封面
    for cat in wp.get_all("wc/v3/products/categories", {"_fields": "id,name,image"}):
        _, brand = find_brand(cat["name"])
        if brand and brand["slug"] in brand_ids and not cat.get("image"):
            wp.req("POST", f"wc/v3/products/categories/{cat['id']}", {"image": {"id": brand_ids[brand["slug"]]}})
            print(f"✓ 分类封面：{cat['name']}")

    def brand_image(p):
        name = next((m["value"] for m in p.get("meta_data", []) if m["key"] == "aurora_brand"), "")
        name = name or next((c["name"] for c in p.get("categories", [])), "")
        _, brand = find_brand(name)
        return brand_ids.get(brand["slug"] if brand else "aurora") or brand_ids.get("aurora")

    def tagged(p, images, source):
        return {"id": p["id"], "images": images, "meta_data": [{"key": "aurora_image_source", "value": source}]}

    local, remote = [], []  # 远程图片要服务器下载，分小批提交
    counts = {"photo": 0, "temp": 0, "brand": 0}
    for p in products:
        sku, src = (p.get("sku") or "").upper(), image_source(p)
        if sku in photos:
            ids = [wp.upload(f, os.path.basename(f), p["name"]) for f in photos[sku]]
            local.append(tagged(p, [{"id": i} for i in ids], "photo"))
            counts["photo"] += 1
        elif sku in web and src != "photo":
            remote.append(tagged(p, [{"src": u, "alt": p["name"]} for u in web[sku]], "temp"))
            counts["temp"] += 1
        elif (not p.get("images") or (clear_temp and src == "temp")) and brand_image(p):
            local.append(tagged(p, [{"id": brand_image(p)}], "brand"))
            counts["brand"] += 1
    for i in range(0, len(local), 50):
        wp.req("POST", "wc/v3/products/batch", {"update": local[i:i + 50]})
    errors = 0
    for i in range(0, len(remote), 5):
        res, _ = wp.req("POST", "wc/v3/products/batch", {"update": remote[i:i + 5]})
        for item in res.get("update", []):
            if item.get("error"):
                errors += 1
                print(f"! 临时图下载失败（产品 {item.get('id')}）：{item['error'].get('message')}")
        print(f"  临时图 {min(i + 5, len(remote))}/{len(remote)}")
    print(f"✓ 实拍图 {counts['photo']} 款，临时图 {counts['temp'] - errors} 款，品牌图 {counts['brand']} 款")


def cmd_menu(wp, dry_run=False):
    if dry_run:
        print("[dry-run] 主导航：" + " / ".join(t for t, _ in MENU))
        return
    menus, _ = wp.req("GET", "wp/v2/menus", params={"_fields": "id,name"})
    if any(m["name"] == "Aurora 主导航" for m in menus):
        print("· 主导航已存在，跳过（要重建请先在后台删除「Aurora 主导航」）")
        return
    menu, _ = wp.req("POST", "wp/v2/menus", {"name": "Aurora 主导航", "locations": ["primary"]})
    for i, (title, path) in enumerate(MENU, 1):
        wp.req("POST", "wp/v2/menu-items", {"title": title, "url": wp.site + path, "menus": menu["id"],
                                            "type": "custom", "status": "publish", "menu_order": i})
    print(f"✓ 已创建主导航（{len(MENU)} 项）并设为 primary 位置")


def cmd_cleanup(wp, dry_run=False):
    plugins, _ = wp.req("GET", "wp/v2/plugins", params={"_fields": "plugin,name,status"})
    for p in plugins:
        if p["plugin"].split("/")[0] in REDUNDANT_PLUGINS and p["status"] == "active":
            if dry_run:
                print(f"[dry-run] 将停用：{p['name']}")
                continue
            wp.req("POST", f"wp/v2/plugins/{p['plugin']}", {"status": "inactive"})
            print(f"✓ 已停用：{p['name']}（可随时在后台重新启用）")


def main():
    ap = argparse.ArgumentParser(description="Aurora Cigars WooCommerce 配置与导入")
    ap.add_argument("command", choices=["check", "configure", "import", "images", "pages", "menu", "cleanup", "all"])
    ap.add_argument("csv", nargs="?", help="产品 CSV 文件（import / all 需要）")
    ap.add_argument("--map", action="append", default=[], metavar="字段=列名",
                    help="手动指定字段映射，例如 --map price=USD售价")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写入网站")
    ap.add_argument("--limit", type=int, help="只导入前 N 行（测试用）")
    ap.add_argument("--photos", metavar="目录", help="images 命令：实拍图目录，文件按 SKU 命名")
    ap.add_argument("--urls", metavar="CSV", help="images 命令：临时图清单（sku,url 两列）")
    ap.add_argument("--clear-temp", action="store_true", help="images 命令：把临时图全部换回品牌图")
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
    if args.command in ("images", "all"):
        cmd_images(wp, args.photos, args.urls, args.clear_temp, args.dry_run)
    if args.command in ("pages", "all"):
        cmd_pages(wp, args.dry_run)
    if args.command in ("menu", "all"):
        cmd_menu(wp, args.dry_run)
    if args.command == "cleanup":
        cmd_cleanup(wp, args.dry_run)


if __name__ == "__main__":
    main()
