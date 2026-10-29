#!/usr/bin/env python3
"""Aurora Cigars 一键配置脚本（只用 Python 标准库）。

用法示例：
  export AURORA_SITE=https://wordpress-1627597-6431471.cloudwaysapps.com
  export AURORA_USER=你的后台登录用户名
  export AURORA_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx'

  python3 aurora_setup.py check                       # 测试连接
  python3 aurora_setup.py install-plugin              # 自动安装/更新并启用 aurora-core（借助 Code Snippets）
  python3 aurora_setup.py configure                   # WooCommerce 设置：USD / 迪拜 / 关闭配送
  python3 aurora_setup.py import aurora_products_full.csv --dry-run   # 先预览字段映射
  python3 aurora_setup.py import aurora_products_full.csv             # 正式导入（按 SKU 去重，可重复跑）
  python3 aurora_setup.py pages                       # 创建首页、关于、防伪查验、FAQ、批发、条款页面，并设为首页
  python3 aurora_setup.py images                      # 给没有图片的产品配品牌图，并设置品牌分类封面
  python3 aurora_setup.py images --photos ~/实拍图     # 按 SKU 命名的实拍图替换（COH-ROB-25.jpg、COH-ROB-25-2.jpg…）
  python3 aurora_setup.py images --urls temp.csv      # 临时网图（sku,url），仅供内部预览
  python3 aurora_setup.py images --clear-temp         # 临时图全部换回品牌图
  python3 aurora_setup.py menu                        # 创建主导航
  python3 aurora_setup.py cleanup                     # 停用 YITH 两个插件 / Click to Chat / PayPal（不在 all 里）
  python3 aurora_setup.py all aurora_products_full.csv
"""

import argparse
import base64
import csv
import difflib
import hashlib
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile

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
REDUNDANT_PLUGINS = ["yith-woocommerce-wishlist", "yith-woocommerce-request-a-quote", "click-to-chat-for-whatsapp",
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

    def get_or_none(self, path, params=None):
        """GET，资源不存在（404）时返回 None 而不是退出。"""
        url = f"{self.site}/wp-json/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        r = urllib.request.Request(url, method="GET", headers=self.headers)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                return json.loads(resp.read().decode() or "null")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise SystemExit(f"✗ GET {path} → HTTP {e.code}\n{e.read().decode(errors='replace')[:600]}")
        except urllib.error.URLError as e:
            raise SystemExit(f"✗ 连接失败 {url}: {e.reason}")

    def delete(self, path, params=None):
        """删除。有的服务器拦截 DELETE 方法，失败时改用 WordPress 支持的 POST + _method=DELETE。"""
        try:
            return self.req("DELETE", path, params=params)[0]
        except SystemExit:
            return self.req("POST", path, {}, params=dict(params or {}, _method="DELETE"))[0]

    def upload(self, file_path, filename, alt):
        with open(file_path, "rb") as f:
            raw = f.read()
        ctype = {".png": "image/png", ".webp": "image/webp"}.get(os.path.splitext(filename)[1].lower(), "image/jpeg")
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
        print("! 还没启用 aurora-core 插件 —— 运行 install-plugin 自动安装")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ZIP = os.path.join(SCRIPT_DIR, "..", "dist", "aurora-core.zip")
PLUGIN_FILE = "aurora-core/aurora-core"


def plugin_active(wp):
    info = wp.get_or_none(f"wp/v2/plugins/{PLUGIN_FILE}", {"_fields": "status,version"})
    return bool(info) and info.get("status") == "active"


def cmd_install_plugin(wp, dry_run=False):
    """借助站点已装的 Code Snippets：临时建一个只有管理员能调用的安装接口，
    用它安装并启用 dist/aurora-core.zip（已安装则覆盖更新），完成后删除这个片段。"""
    if not os.path.exists(PLUGIN_ZIP):
        raise SystemExit(f"✗ 找不到插件包 {PLUGIN_ZIP}，先运行 scripts/build_zip.sh")
    with open(PLUGIN_ZIP, "rb") as f:
        payload = base64.b64encode(f.read()).decode()
    with zipfile.ZipFile(PLUGIN_ZIP) as z:
        local_version = re.search(r"Version:\s*(\S+)", z.read("aurora-core/aurora-core.php").decode()).group(1)
    current = wp.get_or_none(f"wp/v2/plugins/{PLUGIN_FILE}", {"_fields": "status,version"}) or {}
    if not dry_run and current.get("status") == "active" and current.get("version") == local_version:
        print(f"✓ 站点上的 aurora-core 已经是 {local_version} 版，无需更新")
        return
    with open(os.path.join(SCRIPT_DIR, "installer_snippet.php"), encoding="utf-8") as f:
        code = f.read()
    code = code.split("\n", 1)[1].replace("__AURORA_ZIP_BASE64__", payload)  # Code Snippets 不要 <?php 开头
    if dry_run:
        print(f"[dry-run] 将通过 Code Snippets 安装 aurora-core（插件包 {len(payload) * 3 // 4 // 1024} KB）")
        return
    if wp.get_or_none("code-snippets/v1/snippets") is None:
        raise SystemExit("✗ 站点没有启用 Code Snippets（或其接口不可用），无法自动安装。"
                         "请在后台 插件 → 安装插件 → 上传插件，手动上传 dist/aurora-core.zip")
    snippet, _ = wp.req("POST", "code-snippets/v1/snippets", {
        "name": "Aurora 一次性安装器（会自动删除）",
        "desc": "aurora_setup.py install-plugin 临时创建，安装完成后自动删除。",
        "code": code,
        "scope": "global",
        "active": True,
    })
    sid = snippet["id"]
    try:
        if not snippet.get("active"):
            wp.req("POST", f"code-snippets/v1/snippets/{sid}", {"active": True})
        res, _ = wp.req("POST", "aurora-install/v1/run", {})
        print(f"✓ aurora-core 已安装{'并启用' if res.get('active') else '，但未能启用'}")
    finally:
        try:
            wp.delete(f"code-snippets/v1/snippets/{sid}")
            print("✓ 已删除临时安装片段")
        except SystemExit as e:
            print(f"! 临时安装片段（ID {sid}）删除失败，请到后台 Snippets 里手动删除：{e}")
    info = wp.get_or_none(f"wp/v2/plugins/{PLUGIN_FILE}", {"_fields": "status,version"}) or {}
    if info.get("status") != "active":
        raise SystemExit("✗ 安装后检查发现 aurora-core 没有处于启用状态，请到后台 插件 页面查看")
    print(f"✓ 站点上的 aurora-core 现在是 {info.get('version')} 版")


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
            p.pop("status", None)  # 保留现有状态，不把 dedupe 改成草稿的重复款重新发布
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


PAGE_MARKER = "<!-- aurora:managed -->"
BACKUP_DIR = os.path.join(CONTENT_DIR, "backup")


def cmd_pages(wp, dry_run=False, replace=False):
    """创建/更新 Aurora 页面（页面里的短代码依赖 aurora-core，所以插件没启用时拒绝执行）。
    同 slug 的页面如果不是本脚本建的（没有标记），默认跳过、不动站点原有页面；
    加 --replace-pages 时才先把原页面完整备份到 content/backup/，再把它的 slug 改成「-old」（内容不动），然后新建。"""
    if not dry_run and not plugin_active(wp):
        raise SystemExit("✗ aurora-core 插件还没启用，页面里的短代码会原样显示给访客。先运行 install-plugin")
    ids = {}
    for slug, title, filename in PAGES:
        with open(os.path.join(CONTENT_DIR, "pages", filename), encoding="utf-8") as f:
            html = PAGE_MARKER + "\n" + f.read()
        if dry_run:
            print(f"[dry-run] 页面 /{slug}/ {title}")
            continue
        found, _ = wp.req("GET", "wp/v2/pages", params={"slug": slug, "status": "publish,draft,private", "context": "edit"})
        body = {"title": title, "slug": slug, "content": html, "status": "publish"}
        if found and PAGE_MARKER in found[0]["content"]["raw"]:
            res, _ = wp.req("POST", f"wp/v2/pages/{found[0]['id']}", body)
            print(f"✓ 更新页面 /{slug}/")
        elif found and not replace:
            print(f"· /{slug}/ 已是站点原有页面（ID {found[0]['id']}），保留不动")
            continue
        else:
            if found:
                old = found[0]
                os.makedirs(BACKUP_DIR, exist_ok=True)
                path = os.path.join(BACKUP_DIR, f"page-{slug}-{old['id']}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(old, f, ensure_ascii=False, indent=2)
                wp.req("POST", f"wp/v2/pages/{old['id']}", {"slug": f"{slug}-old"})
                print(f"· 原页面 /{slug}/（ID {old['id']}）已备份到 {os.path.relpath(path)}，改名为 /{slug}-old/，内容未动")
            res, _ = wp.req("POST", "wp/v2/pages", body)
            print(f"✓ 新建页面 /{slug}/")
        ids[slug] = res["id"]
    if not dry_run and "home" in ids:
        before, _ = wp.req("GET", "wp/v2/settings", params={"_fields": "show_on_front,page_on_front"})
        print(f"· 原首页设置：{before}（需要恢复时改回这个）")
        wp.req("POST", "wp/v2/settings", {"show_on_front": "page", "page_on_front": ids["home"],
                                          "title": "Aurora Cigars", "description": "古巴雪茄 · 迪拜直供"})
        print("✓ 已设为网站首页")


IMAGE_DIR = os.path.join(CONTENT_DIR, "images")
PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")
ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"}
NAME_META = ("aurora_name_en", "aurora_name_cn", "product_name_zh")
MATCH_MIN, MATCH_MARGIN = 0.86, 0.04


def name_tokens(text):
    """名称比对用的词：去重音、小写，No.2 / No2 / No 2 统一，连续的中文算一个词。
    罗马数字里误打成小写 L 的（Siglo Ill）按 III 处理；连续重复的词只算一次（Punch Punch Punch）。"""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"\bno\.?\s*(?=\d)", "no ", s)
    out = []
    for t in re.findall(r"[a-z]+|\d+|[\u3400-\u9fff]+", s):
        if re.fullmatch(r"[il]{2,4}", t) and "l" in t:
            t = t.replace("l", "i")
        if not out or out[-1] != t:
            out.append(t)
    return out


def name_score(a, b):
    """两个名称的相似度（0–1）。数字和罗马数字必须完全一致：No.1 ≠ No.2，Siglo VI ≠ Siglo V。"""
    strict = lambda t: sorted(x for x in t if x.isdigit() or x in ROMAN)
    if not a or not b or strict(a) != strict(b):
        return 0.0
    ka, kb = "".join(a), "".join(b)
    if ka == kb:
        return 1.0
    sa, sb = set(a), set(b)
    if (sa <= sb or sb <= sa) and min(len(sa), len(sb)) >= 2:
        return 0.9  # 一边多了品牌名或规格词，例如「Behike 52」对「Cohiba Behike BHK 52」
    return difflib.SequenceMatcher(None, ka, kb).ratio()


def walk_photos(photo_dir):
    """照片目录（含子文件夹）里的所有图片，返回按字母排序的相对路径。"""
    out = []
    for root, dirs, files in os.walk(photo_dir, followlinks=True):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if not name.startswith(".") and os.path.splitext(name)[1].lower() in PHOTO_EXT:
                out.append(os.path.relpath(os.path.join(root, name), photo_dir))
    return out


def match_photos(photo_dir, products):
    """实拍图按文件名对应产品：SKU、产品名、英文名、中文名都可以，不分大小写、重音、空格和符号。
    子文件夹名也参与比对（例如「Cohiba/Siglo VI.jpg」）。
    同一款多张图写成「名称 2」「名称-2」「名称 (2)」，第一张做主图，其余进图集。
    同一型号既有上架款又有草稿（重复款）时只配给上架的；两款以上同样接近时不配，列为「不确定」。
    返回 ({产品 id: [文件]}, 对照表行, 未匹配的文件, 不确定的文件)。"""
    def texts(p):
        meta = {m["key"]: m["value"] for m in p.get("meta_data", []) if isinstance(m.get("value"), str)}
        return [t for t in [p.get("sku"), p.get("name"), p.get("aurora_name_cn")] + [meta.get(k) for k in NAME_META] if t]

    live = [p for p in products if p.get("status", "publish") == "publish"]
    keys = [(p, name_tokens(t)) for p in products for t in texts(p)]
    # 已改为草稿的重复款：它的名字（例如中文名）也指向上架的那一款
    for p in products:
        en = next((m["value"] for m in p.get("meta_data", []) if m["key"] == "aurora_name_en"), "")
        if p in live or not en:
            continue
        score, twin = max(((name_score(name_tokens(en), name_tokens(q["name"])), q) for q in live if q is not p),
                          key=lambda x: x[0], default=(0, None))
        if twin and score >= DEDUPE_MIN:
            keys += [(twin, name_tokens(t)) for t in texts(p) if t != p.get("sku")]

    def best_products(text):
        tokens = name_tokens(text)
        scores, hit = {}, {}
        for p, k in keys:
            sc = name_score(tokens, k)
            if sc > scores.get(p["id"], -1):
                scores[p["id"]], hit[p["id"]] = sc, "".join(k)
        # 上架的产品优先：上架款里有对得上的，就不考虑草稿（下架的重复款）
        live_ids = {p["id"] for p in live}
        if any(sc >= MATCH_MIN for pid, sc in scores.items() if pid in live_ids):
            scores = {pid: sc for pid, sc in scores.items() if pid in live_ids}
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        if not ranked or ranked[0][1] < MATCH_MIN:
            return None, 0.0
        best = ranked[0][1]
        top = [pid for pid, sc in ranked if sc >= best - MATCH_MARGIN]
        # 站点里有完全同名的两款（例如两个 Cohiba Siglo VI）时两款都配；否则只接受唯一的一款
        same = all(scores[pid] == best for pid in top) and len({hit[pid] for pid in top}) == 1
        return (top if len(top) == 1 or same else []), best  # 有两款以上分数接近 → 不确定，留给人工核对

    groups, rows, unmatched, unsure = {}, [], [], []
    for name in walk_photos(photo_dir):
        stem = os.path.splitext(os.path.basename(name))[0]
        folder = os.path.basename(os.path.dirname(name))
        tries = [(stem, 1)]
        m = re.match(r"^(.*?)[\s_\-]*\(?(\d{1,2})\)?$", stem)
        if m and m.group(1).strip():
            tries.append((m.group(1), int(m.group(2))))  # 末尾的序号当作图集顺序
        if folder:  # 文件名对不上时，加上所在文件夹的名字再试（文件夹常常是品牌或型号）
            tries += [(f"{folder} {t}", o) for t, o in tries]
        result = None
        for text, order in tries:
            pids, score = best_products(text)
            if pids:
                result = (pids, order, score)
                break
            if pids == []:
                result = ([], order, score)
        if not result:
            unmatched.append(name)
            rows.append({"file": name, "status": "未匹配"})
            continue
        pids, order, score = result
        if not pids:
            unsure.append(name)
            rows.append({"file": name, "status": "不确定（有多个相近的产品）"})
            continue
        for pid in pids:
            groups.setdefault(pid, []).append((order, os.path.join(photo_dir, name)))
            p = next(x for x in products if x["id"] == pid)
            rows.append({"file": name, "status": "已匹配", "product_id": pid, "sku": p.get("sku", ""),
                         "product": p["name"], "order": order, "score": round(score, 2)})
    return {k: [f for _, f in sorted(v)] for k, v in groups.items()}, rows, unmatched, unsure


STRIP_RATIO = 2  # 长宽比超过 2 的横条图（单支雪茄的侧面照）
PAD = 1.12  # 横条图放到正方形画布上时两端各留约 6% 白边（产品页相框内有一圈细线，太窄会压到雪茄两端）


def image_size(path):
    """图片宽高，读不出时返回 (None, None)。Mac 上用系统自带的 sips，否则用 Pillow。"""
    if shutil.which("sips"):
        out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path], capture_output=True, text=True).stdout
        w, h = re.search(r"pixelWidth:\s*(\d+)", out), re.search(r"pixelHeight:\s*(\d+)", out)
        return (int(w.group(1)), int(h.group(1))) if w and h else (None, None)
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None, None


def prepare_photo(path):
    """生成上传用的副本，原图不动：HEIC 转 JPG，大于 2.5MB 的重新压缩（长边最多 2000px）；
    单支雪茄的横条图放到白底正方形画布正中，网站按正方形裁切缩略图时才能显示整支雪茄。其他情况原样上传。"""
    ext = os.path.splitext(path)[1].lower()
    heic = ext in (".heic", ".heif")
    w, h = image_size(path)
    strip = bool(w and h and max(w, h) > STRIP_RATIO * min(w, h))
    if not (heic or strip or os.path.getsize(path) > 2.5 * 1024 * 1024):
        return path, ext
    longest, limit = max(w or 0, h or 0), (1800 if strip else 2000)  # 横条图补边后长边约为 1.12 倍
    out = os.path.join(tempfile.mkdtemp(prefix="aurora-photo-"), "photo.jpg")
    if shutil.which("sips"):
        cmd = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85"]
        if longest > limit:  # 只缩小不放大
            cmd += ["-Z", str(limit)]
        subprocess.run(cmd + [path, "--out", out], check=True, capture_output=True)
        if strip:
            side = str(round(max(image_size(out)) * PAD))
            subprocess.run(["sips", "-p", side, side, "--padColor", "FFFFFF", "-s", "formatOptions", "85", out, "--out", out],
                           check=True, capture_output=True)
        return out, ".jpg"
    try:
        from PIL import Image
    except ImportError:
        if heic:
            raise SystemExit(f"✗ {os.path.basename(path)} 是 HEIC 格式，这台电脑没有 sips，无法转换成 JPG")
        return path, ext
    with Image.open(path) as im:
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, "white")  # 透明背景铺白
        flat.paste(im, mask=im.getchannel("A"))
        if longest > limit:
            flat.thumbnail((limit, limit))
        if strip:
            side = round(max(flat.size) * PAD)
            canvas = Image.new("RGB", (side, side), "white")
            canvas.paste(flat, ((side - flat.width) // 2, (side - flat.height) // 2))
            flat = canvas
        flat.save(out, "JPEG", quality=85)
    return out, ".jpg"


def file_sha1(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def find_photo(photo_dir, rel, index, sha1=""):
    """对照表里的照片，返回 (路径, 找不到的原因)。拖进多个文件夹时汇总目录多了一层文件夹名，所以也按文件名找；
    几个文件夹里有同名照片时，按核对时记下的指纹（sha1）认出核对过的那一张，内容对不上的不用。"""
    hits = [rel] if os.path.isfile(os.path.join(photo_dir, rel)) else []
    hits += [h for h in index.get(unicodedata.normalize("NFC", os.path.basename(rel)), []) if h not in hits]
    if not hits:
        return None, "找不到照片"
    paths = [os.path.join(photo_dir, h) for h in hits]
    if sha1:
        match = next((f for f in paths if file_sha1(f) == sha1), None)
        return (match, "") if match else (None, f"照片内容和核对时不一样（同名的 {len(paths)} 张都对不上）")
    if len(paths) == 1 or len({file_sha1(f) for f in paths}) == 1:
        return paths[0], ""
    return None, f"有 {len(paths)} 张同名照片且内容不同，不知道用哪张"


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


SAVE_BATCH = 10  # 网站每保存一款产品都要通知 Google / Pinterest 等营销插件，一次存太多容易超时


def save_products(wp, items, label="保存"):
    """分小批保存产品修改，每批后显示进度。重新运行各命令时已改好的会被跳过，中途断了可以直接重跑。"""
    for i in range(0, len(items), SAVE_BATCH):
        res, _ = wp.req("POST", "wc/v3/products/batch", {"update": items[i:i + SAVE_BATCH]})
        for it in (res or {}).get("update", []):
            if it.get("error"):
                print(f"! 产品 {it.get('id')} 没有保存成功：{it['error'].get('message')}")
        if len(items) > SAVE_BATCH:
            print(f"  已{label} {min(i + SAVE_BATCH, len(items))}/{len(items)}")


def image_source(p):
    return next((m["value"] for m in p.get("meta_data", []) if m["key"] == "aurora_image_source"), "")


def cmd_images(wp, photo_dir=None, url_csv=None, clear_temp=False, dry_run=False):
    """图片来源优先级：实拍图（photo）> 临时网图（temp）> 品牌渲染图（brand）。
    每款产品记录 aurora_image_source，便于之后整批替换临时图。"""
    if photo_dir and not os.path.isdir(photo_dir):
        raise SystemExit(f"✗ 找不到图片目录：{photo_dir}")
    brand_ids = brand_media(wp, dry_run)
    products = wp.get_all("wc/v3/products", {"_fields": "id,sku,name,aurora_name_cn,status,images,categories,meta_data",
                                             "status": "any"})
    skus = {(p.get("sku") or "").upper() for p in products if p.get("sku")}
    photos = {}
    if photo_dir:
        photos, rows, unmatched, unsure = match_photos(photo_dir, products)
        has_photo = {p["id"] for p in products if image_source(p) == "photo"}
        skipped = [pid for pid in photos if pid in has_photo]
        photos = {pid: f for pid, f in photos.items() if pid not in has_photo}
        total = len([r for r in rows if r["status"] != "已匹配"]) + len({r["file"] for r in rows if r["status"] == "已匹配"})
        print(f"实拍图 {total} 张：对上 {len(photos) + len(skipped)} 款产品，未匹配 {len(unmatched)} 张，不确定 {len(unsure)} 张")
        if skipped:
            print(f"· 其中 {len(skipped)} 款已经有实拍图，这次不重复上传")
        for name in unmatched:
            print(f"! 未匹配：{name}")
        for name in unsure:
            print(f"? 不确定：{name}")
        report = os.path.expanduser("~/Desktop/aurora-实拍图对照表.csv")
        report = report if os.path.isdir(os.path.dirname(report)) else os.path.abspath("aurora-实拍图对照表.csv")
        with open(report, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, ["file", "status", "product_id", "sku", "product", "order", "score"])
            w.writeheader()
            w.writerows(rows)
        print(f"· 对照表：{report}（可以用 Numbers / Excel 打开核对）")
    web = read_image_urls(url_csv) if url_csv else {}
    if url_csv:
        print(f"临时图清单：{len(web)} 个 SKU" + "".join(f"\n! 清单里的 SKU 不存在：{k}" for k in web if k not in skus))
    if dry_run:
        by_id = {p["id"]: p for p in products}
        for pid, files in photos.items():
            print(f"[dry-run] {by_id[pid]['name']} ← {', '.join(os.path.basename(f) for f in files)}")
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

    uploaded = {}  # 同一个文件配给多款时只上传一次

    def upload_photo(path, p, n):
        if path not in uploaded:
            src, ext = prepare_photo(path)
            base = re.sub(r"[^A-Za-z0-9-]+", "-", p.get("sku") or f"product-{p['id']}").strip("-")
            uploaded[path] = wp.upload(src, f"{base}{'' if n == 1 else f'-{n}'}{ext}", p["name"])
        return uploaded[path]

    local, remote = [], []  # 远程图片要服务器下载，分小批提交
    counts = {"photo": 0, "temp": 0, "brand": 0}
    done = 0
    for p in products:
        sku, src = (p.get("sku") or "").upper(), image_source(p)
        if p["id"] in photos:
            ids = [upload_photo(f, p, n) for n, f in enumerate(photos[p["id"]], 1)]
            local.append(tagged(p, [{"id": i} for i in ids], "photo"))
            counts["photo"] += 1
            done += 1
            print(f"  实拍图 {done}/{len(photos)}：{p['name']}")
        elif sku in web and src != "photo":
            remote.append(tagged(p, [{"src": u, "alt": p["name"]} for u in web[sku]], "temp"))
            counts["temp"] += 1
        elif (not p.get("images") or (clear_temp and src == "temp")) and brand_image(p):
            local.append(tagged(p, [{"id": brand_image(p)}], "brand"))
            counts["brand"] += 1
    save_products(wp, local)
    errors = 0
    for i in range(0, len(remote), 5):
        res, _ = wp.req("POST", "wc/v3/products/batch", {"update": remote[i:i + 5]})
        for item in res.get("update", []):
            if item.get("error"):
                errors += 1
                print(f"! 临时图下载失败（产品 {item.get('id')}）：{item['error'].get('message')}")
        print(f"  临时图 {min(i + 5, len(remote))}/{len(remote)}")
    print(f"✓ 实拍图 {counts['photo']} 款，临时图 {counts['temp'] - errors} 款，品牌图 {counts['brand']} 款")


PHOTO_ROLES = {"主图": 0, "包装": 1, "本体": 2, "细节": 3, "其他": 4}


def photo_info(path):
    """图片尺寸和一份缩略图副本（长边 1000px，JPG）。Mac 上用系统自带的 sips；没有 sips 时尽量用 Pillow。
    只读原图，不改动原文件。"""
    width = height = None
    thumb = None
    if shutil.which("sips"):
        width, height = image_size(path)
        tmp = os.path.join(tempfile.mkdtemp(prefix="aurora-thumb-"), "t.jpg")
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "75", "-Z", "1000", path, "--out", tmp],
                           capture_output=True)
        if r.returncode == 0 and os.path.exists(tmp):
            thumb = open(tmp, "rb").read()
    else:
        try:
            from PIL import Image
            import io
            with Image.open(path) as im:
                width, height = im.size
                im = im.convert("RGB")
                im.thumbnail((1000, 1000))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=75)
                thumb = buf.getvalue()
        except Exception:
            pass
    return width, height, thumb


def product_snapshot(products):
    """产品现有图片的快照：用于备份和还原。"""
    return [{"id": p["id"], "sku": p.get("sku", ""), "name": p["name"], "status": p.get("status"),
             "image_source": image_source(p),
             "images": [{"id": i.get("id"), "src": i.get("src", "")} for i in p.get("images") or []]} for p in products]


def save_backup(products, label):
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M")
    path = os.path.expanduser(f"~/Desktop/aurora-产品图片备份-{label}-{stamp}.json")
    path = path if os.path.isdir(os.path.dirname(path)) else os.path.abspath(os.path.basename(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(product_snapshot(products), f, ensure_ascii=False, indent=1)
    return path


def cmd_photo_inventory(wp, photo_dir, out_path):
    """第 1 步（只读，不改网站，不改原图）：清点照片目录及子文件夹，记录路径、大小、尺寸、指纹（找重复文件），
    做缩略图副本，附上网站现有产品清单和按文件名的初步建议，打包给 Claude 逐张核对。同时备份产品现有图片。"""
    if not photo_dir or not os.path.isdir(photo_dir):
        raise SystemExit(f"✗ 找不到照片文件夹：{photo_dir}")
    files = walk_photos(photo_dir)
    if not files:
        raise SystemExit("✗ 这个文件夹里没有图片（支持 jpg / jpeg / png / webp / heic）")
    products = wp.get_all("wc/v3/products", {"_fields": "id,sku,name,aurora_name_cn,status,categories,images,meta_data,"
                                                        "regular_price,stock_status", "status": "any"})
    _, rows, _, _ = match_photos(photo_dir, products)
    suggest = {}
    for r in rows:
        suggest.setdefault(r["file"], []).append(r)
    backup = save_backup(products, "清点时")
    seen, manifest = {}, []
    out_path = os.path.expanduser(out_path)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, rel in enumerate(files, 1):
            full = os.path.join(photo_dir, rel)
            raw = open(full, "rb").read()
            digest = hashlib.sha1(raw).hexdigest()
            width, height, thumb = photo_info(full)
            thumb_name = f"thumbs/{n:04d}.jpg" if thumb else ""
            if thumb:
                z.writestr(thumb_name, thumb)
            hits = suggest.get(rel, [])
            manifest.append({
                "no": n, "file": rel, "folder": os.path.dirname(rel), "bytes": len(raw), "width": width, "height": height,
                "sha1": digest, "duplicate_of": seen.get(digest, ""), "thumb": thumb_name,
                "suggest": hits[0]["status"] if hits else "",
                "suggest_sku": " | ".join(h.get("sku", "") for h in hits if h.get("sku")),
                "suggest_product": " | ".join(h.get("product", "") for h in hits if h.get("product")),
            })
            seen.setdefault(digest, rel)
            if n % 20 == 0 or n == len(files):
                print(f"  已清点 {n}/{len(files)}")
        buf = __import__("io").StringIO()
        w = csv.DictWriter(buf, list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)
        z.writestr("manifest.csv", "﻿" + buf.getvalue())
        cats = lambda p: [c.get("name") for c in p.get("categories", [])]
        z.writestr("products.json", json.dumps([dict(snap, categories=cats(p), price=p.get("regular_price"),
                                                     stock=p.get("stock_status"), name_cn=p.get("aurora_name_cn", ""),
                                                     name_en=next((m["value"] for m in p.get("meta_data", [])
                                                                   if m["key"] == "aurora_name_en"), ""))
                                                for snap, p in zip(product_snapshot(products), products)],
                                               ensure_ascii=False, indent=1))
    dups = sum(1 for m in manifest if m["duplicate_of"])
    print(f"\n✓ 图片 {len(files)} 张（其中内容完全相同的重复文件 {dups} 张），网站产品 {len(products)} 款")
    print(f"✓ 清单包：{out_path}（{os.path.getsize(out_path) // 1024} KB）")
    print(f"✓ 产品现有图片已备份：{backup}")
    print("  原始照片没有任何改动，网站也没有任何改动。")


def cmd_photo_apply(wp, photo_dir, mapping_csv, dry_run=False):
    """第 2 步：按核对确认后的对照表给产品配图，只处理状态为「确认」的行。
    同一产品的图按 主图 → 包装 → 本体 → 细节 → 其他 排列：第一张是产品主图，其余进产品图库。
    先在桌面备份这些产品现有的图片；上传的是转换/缩小后的副本，原始照片不改动。"""
    if not photo_dir or not os.path.isdir(photo_dir):
        raise SystemExit(f"✗ 找不到照片文件夹：{photo_dir}")
    with open(mapping_csv, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f)]
    todo = [r for r in rows if r.get("status", "").strip() == "确认"]
    held = len(rows) - len(todo)
    products = wp.get_all("wc/v3/products", {"_fields": "id,sku,name,status,images,meta_data", "status": "any"})
    by_sku = {(p.get("sku") or "").upper(): p for p in products if p.get("sku")}
    index = {}
    for rel in walk_photos(photo_dir):
        index.setdefault(unicodedata.normalize("NFC", os.path.basename(rel)), []).append(rel)
    with open(os.path.join(CONTENT_DIR, "new-products.csv"), newline="", encoding="utf-8") as f:
        to_create = {r["sku"].upper() for r in csv.DictReader(f)}
    plan, problems, later = {}, [], set()
    for r in todo:
        p = by_sku.get(r["sku"].strip().upper())
        full, why = find_photo(photo_dir, r["file"], index, (r.get("sha1") or "").strip())
        if not p and dry_run and r["sku"].strip().upper() in to_create:
            later.add(r["sku"].strip().upper())  # 预览时还没新建，正式运行前 create-drafts 会先建好
        elif not p:
            problems.append(f"网站上没有 SKU {r['sku']}（{r['file']}）")
        elif not full:
            problems.append(f"{why}：{r['file']}")
        else:
            key = (PHOTO_ROLES.get(r.get("role", "").strip(), 4), int(r.get("order") or 1))
            plan.setdefault(p["id"], (p, []))[1].append((key, full, r))
    print(f"对照表 {len(rows)} 行：确认 {len(todo)} 行，待确认/不上传 {held} 行（这次不处理）")
    for msg in problems:
        print(f"! {msg}")
    if problems:
        print(f"（照片文件夹里共找到 {sum(len(v) for v in index.values())} 张图片）")
        raise SystemExit("✗ 对照表和网站或照片文件夹对不上，先不上传。请把这几行发给 Claude。")
    meta = lambda p, k: next((m["value"] for m in p.get("meta_data", []) if m["key"] == k), "")
    files_of = lambda items: "|".join(os.path.basename(r["file"]) for _, _, r in items)
    for p, items in plan.values():
        items.sort(key=lambda x: x[0])
    done_before = [pid for pid, (p, items) in plan.items()
                   if image_source(p) == "photo" and meta(p, "aurora_photo_files") == files_of(items)]
    for pid in done_before:  # 重新运行时，已经按同样照片配好的产品不再重复上传
        del plan[pid]
    print(f"将更新 {len(plan)} 款产品，共 {sum(len(v[1]) for v in plan.values())} 张图"
          + (f"（另有 {len(done_before)} 款之前已配好，跳过）" if done_before else "")
          + (f"；另有 {len(later)} 款新建草稿后再配图" if later else ""))
    for p, items in plan.values():
        print(f"  {p['sku']:<14} {p['name']}：" + "，".join(f"{r.get('role') or '其他'} {os.path.basename(r['file'])}"
                                                       for _, _, r in items))
    if dry_run or not plan:
        return
    backup = save_backup([p for p, _ in plan.values()], "上传前")
    print(f"✓ 这些产品现有的图片已备份：{backup}")
    uploaded, pending, saved, failed = {}, [], 0, []
    for done, (p, items) in enumerate(plan.values(), 1):
        ids = []
        try:
            for n, (_, full, _) in enumerate(items, 1):
                if full not in uploaded:
                    src, ext = prepare_photo(full)
                    base = re.sub(r"[^A-Za-z0-9-]+", "-", p["sku"]).strip("-")
                    uploaded[full] = wp.upload(src, f"{base}{'' if n == 1 else f'-{n}'}{ext}", p["name"])
                ids.append(uploaded[full])
        except (SystemExit, OSError, subprocess.CalledProcessError) as e:  # 一款失败不影响其他款
            failed.append(p)
            print(f"! {p['sku']} {p['name']} 上传失败：{e}")
            if len(failed) >= 5 and not saved and not pending:
                print("✗ 前 5 款都上传失败，先停下。请把上面的报错截图发给 Claude。")
                break
            continue
        pending.append({"id": p["id"], "images": [{"id": i} for i in ids],
                        "meta_data": [{"key": "aurora_image_source", "value": "photo"},
                                      {"key": "aurora_photo_files", "value": files_of(items)}]})
        print(f"  已上传 {done}/{len(plan)}：{p['name']}（{len(ids)} 张）")
        if len(pending) == SAVE_BATCH or done == len(plan):  # 每 10 款保存一次，中途断了重跑会接着做
            save_products(wp, pending, "关联图片")
            saved, pending = saved + len(pending), []
    if pending:
        save_products(wp, pending, "关联图片")
        saved += len(pending)
    print(f"\n✓ 已更新 {saved} 款产品，上传 {len(uploaded)} 张图片。需要撤销时运行：run_photos.sh restore {backup}")
    if failed:
        print(f"! 有 {len(failed)} 款没有上传成功：" + "、".join(p["sku"] for p in failed) + "（重新运行同一条命令会只补这几款）")


def cmd_photo_restore(wp, backup_json):
    """按备份把产品名称、图片和上架/草稿状态恢复成备份时的样子（图片文件仍在媒体库里，只是重新关联）。"""
    with open(os.path.expanduser(backup_json), encoding="utf-8") as f:
        snap = json.load(f)
    updates = [dict({"id": p["id"], "name": p["name"], "images": [{"id": i["id"]} for i in p["images"] if i.get("id")],
                     "meta_data": [{"key": "aurora_image_source", "value": p.get("image_source") or ""}]},
                    **({"status": p["status"]} if p.get("status") else {})) for p in snap]
    save_products(wp, updates, "恢复")
    print(f"✓ 已把 {len(updates)} 款产品的名称、图片和上架状态恢复为备份时的样子")


def cmd_rename(wp, dry_run=False):
    """按 content/name-fixes.csv 修正写错的产品名称（field 为 name 或某个英文名字段）。
    只改当前值仍等于表里「原值」的产品，已经被人改过的不动；产品网址（slug）不变。
    修改前的名称在清点备份里，photo-restore 可以恢复。"""
    with open(os.path.join(CONTENT_DIR, "name-fixes.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    products = wp.get_all("wc/v3/products", {"_fields": "id,sku,name,meta_data", "status": "any"})
    by_sku = {(p.get("sku") or "").upper(): p for p in products if p.get("sku")}
    norm = lambda t: re.sub(r"\s+", " ", str(t or "")).strip()
    updates, already, skipped = {}, 0, 0
    for r in rows:
        p = by_sku.get(r["sku"].upper())
        if not p:
            print(f"· 网站上没有 {r['sku']}，跳过")
            continue
        field = r.get("field") or "name"
        cur = p["name"] if field == "name" else next((m["value"] for m in p.get("meta_data", []) if m["key"] == field), "")
        if str(cur or "").strip() == r["new"]:  # 精确比较：只差换行的名字也要改
            already += 1
            continue
        if norm(cur) != norm(r["old"]):
            print(f"! {r['sku']} 现在是「{norm(cur)}」，和表里的原值不同（可能已经改过），不动")
            skipped += 1
            continue
        u = updates.setdefault(p["id"], {"id": p["id"]})
        if field == "name":
            u["name"] = r["new"]
        else:
            u.setdefault("meta_data", []).append({"key": field, "value": r["new"]})
        print(f"  {r['sku']:<11} {norm(cur)} → {r['new']}（{r['reason']}）")
    print(f"名称修正：要改 {len(updates)} 款，已经是正确名称 {already} 项，跳过 {skipped} 项")
    if dry_run or not updates:
        return
    items = list(updates.values())
    save_products(wp, items, "保存名称")
    print(f"✓ 已修正 {len(items)} 款产品的名称（产品网址不变）")


MERGE_FIELDS = ("regular_price", "sale_price", "description", "short_description", "weight")
OWN_META = {"aurora_merged_into", "aurora_image_source", "aurora_review"}  # 本脚本自己的标记，不当作产品资料合并


def cmd_merge(wp, dry_run=False):
    """站点原有产品里完全同名的重复款合并：每组保留资料最全的一款（同样全时保留编号小的，也就是最早的网址），
    另一款有、保留款缺的资料（价格、描述、库存数量、图片、分类、自定义字段）补到保留款上，
    再把另一款改为草稿并记下 aurora_merged_into。不删除任何产品。"""
    with open(os.path.join(CONTENT_DIR, "catalog.csv"), newline="", encoding="utf-8") as f:
        ours = {r["SKU"] for r in csv.DictReader(f)}
    products = wp.get_all("wc/v3/products", {"status": "publish", "_fields": "id,sku,name,status,images,categories,"
                                              "meta_data,manage_stock,stock_quantity," + ",".join(MERGE_FIELDS)})
    groups = {}
    for p in products:
        if p.get("sku") not in ours and p.get("status") == "publish":  # 已改草稿的不再参与，重复运行不会出错
            groups.setdefault("".join(name_tokens(p["name"])), []).append(p)
    groups = [g for g in groups.values() if len(g) > 1]
    if not groups:
        print("没有同名重复的产品")
        return

    def richness(p):
        meta = [m for m in p.get("meta_data", []) if not m["key"].startswith("_") and m["key"] not in OWN_META
                and m.get("value") not in ("", None)]
        return sum(1 for k in MERGE_FIELDS if p.get(k)) + len(p.get("images") or []) + len(meta) + (1 if p.get("manage_stock") else 0)

    num = lambda p: int(re.sub(r"\D", "", p.get("sku") or "") or 10 ** 9)
    keep_updates, drafts = [], []
    for g in groups:
        keeper = max(g, key=lambda p: (richness(p), -num(p)))
        fill, meta_have = {}, {m["key"] for m in keeper.get("meta_data", [])}
        for other in (p for p in g if p is not keeper):
            for k in MERGE_FIELDS:
                if not keeper.get(k) and other.get(k) and k not in fill:
                    fill[k] = other[k]
            if not keeper.get("manage_stock") and other.get("manage_stock") and "stock_quantity" not in fill:
                fill.update(manage_stock=True, stock_quantity=other.get("stock_quantity"))
            if not keeper.get("images") and other.get("images") and "images" not in fill:
                fill["images"] = [{"id": i["id"]} for i in other["images"]]
            cats = {c["id"] for c in keeper.get("categories", [])}
            extra = [c for c in other.get("categories", []) if c["id"] not in cats]
            if extra:
                fill["categories"] = [{"id": c["id"]} for c in keeper.get("categories", []) + extra]
            for m in other.get("meta_data", []):
                if (not m["key"].startswith("_") and m["key"] not in OWN_META and m["key"] not in meta_have
                        and m.get("value") not in ("", None)):
                    fill.setdefault("meta_data", []).append({"key": m["key"], "value": m["value"]})
                    meta_have.add(m["key"])
            drafts.append({"id": other["id"], "status": "draft",
                           "meta_data": [{"key": "aurora_merged_into", "value": keeper.get("sku") or str(keeper["id"])}]})
            print(f"  {other.get('sku')} {other['name']} → 合并到 {keeper.get('sku')}（{other.get('sku')} 改为草稿）")
        if fill:
            keep_updates.append(dict(fill, id=keeper["id"]))
            print(f"    {keeper.get('sku')} 补上：{', '.join(k for k in fill if k != 'id')}")
    print(f"同名重复 {len(groups)} 组，{len(drafts)} 款改为草稿")
    if dry_run:
        return
    save_products(wp, keep_updates + drafts)
    print(f"✓ 已合并（改为草稿的产品在后台 产品 → 草稿 里，可以随时恢复）")


def cmd_create_drafts(wp, dry_run=False):
    """content/new-products.csv 里站上原来没有的产品（照片里的地区限量、特别版等）新建为草稿：
    只有名称和分类，价格、规格、库存留空，不对外显示；照片由 photo-apply 配上，标红由 mark-review 加上。
    已有同一 SKU 的跳过；已有同名产品（不同 SKU）的也不建，避免重复。"""
    with open(os.path.join(CONTENT_DIR, "new-products.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    products = wp.get_all("wc/v3/products", {"status": "any", "_fields": "id,sku,name"})
    skus = {(p.get("sku") or "").upper() for p in products}
    names = {"".join(name_tokens(p["name"])): p for p in products}
    cats = {c["slug"]: c["id"] for c in wp.get_all("wc/v3/products/categories", {"_fields": "id,slug"})}
    todo = []
    for r in rows:
        if r["sku"].upper() in skus:
            continue
        twin = names.get("".join(name_tokens(r["name"])))
        if twin:
            print(f"! {r['sku']} {r['name']}：网站上已有同名的 {twin.get('sku')}，不新建")
            continue
        slugs = [s for s in r["categories"].split("|") if s]
        for s in slugs:
            if s not in cats:
                print(f"! {r['sku']}：网站上没有分类 {s}，这个分类先不加")
        todo.append({"sku": r["sku"], "name": r["name"], "status": "draft", "type": "simple",
                     "categories": [{"id": cats[s]} for s in slugs if s in cats],
                     "meta_data": [{"key": "aurora_created_from", "value": "photo"}]})
        print(f"  新建草稿 {r['sku']}  {r['name']}")
    print(f"新建草稿：{len(todo)} 款（表里共 {len(rows)} 款，其余已存在）")
    if dry_run or not todo:
        return
    for i in range(0, len(todo), SAVE_BATCH):
        res, _ = wp.req("POST", "wc/v3/products/batch", {"create": todo[i:i + SAVE_BATCH]})
        for it in (res or {}).get("create", []):
            if it.get("error"):
                print(f"! 有一款没有建成功：{it['error'].get('message')}")
        if len(todo) > SAVE_BATCH:
            print(f"  已新建 {min(i + SAVE_BATCH, len(todo))}/{len(todo)}")
    print("✓ 已新建为草稿（后台 产品 → 草稿 里可以看到，名称标红；补好资料后再发布）")


def cmd_mark_review(wp, dry_run=False):
    """content/name-review.csv 里拿不准官方名称的产品：写入 aurora_review，前台和后台把名称标红，等人工核对。
    核对完把那一行从表里删掉再运行一次，标记就会清除。"""
    with open(os.path.join(CONTENT_DIR, "name-review.csv"), newline="", encoding="utf-8") as f:
        rows = {r["sku"].upper(): r for r in csv.DictReader(f)}
    products = wp.get_all("wc/v3/products", {"status": "any", "_fields": "id,sku,name,meta_data"})
    updates = []
    for p in products:
        sku = (p.get("sku") or "").upper()
        cur = next((m["value"] for m in p.get("meta_data", []) if m["key"] == "aurora_review"), "")
        want = rows[sku]["note"] if sku in rows else ""
        if cur != want:
            updates.append({"id": p["id"], "meta_data": [{"key": "aurora_review", "value": want}]})
            print(f"  {'标红' if want else '取消标红'}：{p.get('sku')} {p['name']}" + (f"（{want}）" if want else ""))
    missing = set(rows) - {(p.get("sku") or "").upper() for p in products}
    for sku in sorted(missing):
        print(f"! 网站上没有 {sku}")
    print(f"待核对名称：{len(rows)} 款，这次变更 {len(updates)} 款")
    if dry_run or not updates:
        return
    save_products(wp, updates, "标记")
    print("✓ 已标记（只在内部预览模式下或管理员登录时显示红色）")


def cmd_audit(wp, out_path):
    """只读诊断：收集主题、插件、代码片段、产品/分类统计和前台页面 HTML + 同站 CSS，
    打包成 zip，方便在别处还原页面效果、排查设计冲突和重复产品。不修改站点任何内容。"""
    report, files = {}, {}

    def section(name, fn):
        try:
            report[name] = fn()
            print(f"✓ {name}")
        except (SystemExit, Exception) as e:  # 某一项失败不影响其他项
            report[name] = {"error": str(e)[:500]}
            print(f"! {name}：{str(e)[:120]}")

    section("site", lambda: wp.req("GET", "wp/v2/settings",
                                   params={"_fields": "title,description,url,show_on_front,page_on_front"})[0])
    section("theme", lambda: [{k: t.get(k) for k in ("stylesheet", "template", "name", "version")}
                              for t in wp.req("GET", "wp/v2/themes", params={"status": "active"})[0]])
    section("plugins", lambda: [{k: p.get(k) for k in ("plugin", "name", "version", "status")}
                                for p in wp.req("GET", "wp/v2/plugins")[0]])
    section("snippets", lambda: [{k: sn.get(k) for k in ("id", "name", "desc", "scope", "active", "priority", "code")}
                                 for sn in (wp.get_or_none("code-snippets/v1/snippets") or [])])
    section("categories", lambda: wp.get_all("wp/v2/product_cat", {"_fields": "id,name,slug,parent,count,link"}))
    section("pages", lambda: wp.get_all("wp/v2/pages", {"_fields": "id,slug,title,status,link,template,parent",
                                                         "status": "publish,draft,private"}))

    def products():
        rows = wp.get_all("wc/v3/products", {"status": "any",
                                             "_fields": "id,name,sku,status,stock_status,permalink,categories,images,meta_data"})
        with open(os.path.join(CONTENT_DIR, "catalog.csv"), newline="", encoding="utf-8") as f:
            ours = {r["SKU"] for r in csv.DictReader(f)}
        names = {}
        for p in rows:
            names.setdefault(re.sub(r"\s+", "", p.get("name", "")).lower(), []).append(p["id"])
        return {
            "total": len(rows),
            "from_catalog_csv": sum(1 for p in rows if p.get("sku") in ours),
            "duplicate_names": {k: v for k, v in names.items() if len(v) > 1},
            "items": [{
                "id": p["id"], "name": p.get("name"), "sku": p.get("sku"), "status": p.get("status"),
                "stock": p.get("stock_status"), "link": p.get("permalink"),
                "cats": [c.get("name", c.get("id")) for c in p.get("categories", [])],
                "images": len(p.get("images") or []),
                "image_srcs": [i.get("src", "") for i in p.get("images") or []],
                "ours": p.get("sku") in ours,
                "meta": {m["key"]: m["value"] for m in p.get("meta_data", [])
                         if isinstance(m.get("value"), (str, int, float)) and not m["key"].startswith("_")},
            } for p in rows],
        }
    section("products", products)

    def image_check():
        """实拍图逐张试加载（HEAD 请求），找出破损的图片链接。"""
        items = report.get("products", {}).get("items", []) if isinstance(report.get("products"), dict) else []
        out = []
        for p in items:
            if p.get("meta", {}).get("aurora_image_source") != "photo":
                continue
            for src in p.get("image_srcs", []):
                try:
                    with urllib.request.urlopen(urllib.request.Request(src, method="HEAD"), timeout=30) as r:
                        status, ctype = r.status, r.headers.get("Content-Type", "")
                except Exception as e:
                    status, ctype = getattr(e, "code", str(e)[:80]), ""
                out.append({"id": p["id"], "sku": p.get("sku"), "src": src, "status": status, "type": ctype})
        bad = [x for x in out if x["status"] != 200 or not str(x["type"]).startswith("image/")]
        return {"checked": len(out), "broken": bad}
    section("image_check", image_check)

    # 前台页面：用预览密钥以访客身份抓取，并下载同站 CSS
    key = (wp.get_or_none("wp/v2/settings", {"_fields": "aurora_preview_key"}) or {}).get("aurora_preview_key", "")
    host = urllib.parse.urlparse(wp.site).netloc
    targets = [("home", wp.site + "/")]
    shop = wp.get_or_none("wc/v3/settings/products/woocommerce_shop_page_id")
    if shop and shop.get("value"):
        page = wp.get_or_none(f"wp/v2/pages/{shop['value']}", {"_fields": "link"})
        if page:
            targets.append(("shop", page["link"]))
    cats = report.get("categories")
    if isinstance(cats, list) and cats:
        top = max(cats, key=lambda c: c.get("count", 0))
        targets.append(("category", top["link"]))
    prods = report.get("products", {}).get("items", []) if isinstance(report.get("products"), dict) else []
    for label, want_ours in (("product_existing", False), ("product_catalog", True)):
        hit = next((p for p in prods if p["ours"] == want_ours and p["status"] == "publish" and p.get("link")), None)
        if hit:
            targets.append((label, hit["link"]))
    # 站点其他已发布页面（关于、常见问题、批发、限量……），用来检查手写页面的效果
    skip = {"shop", "cart", "checkout", "my-account"}
    pages = report.get("pages") if isinstance(report.get("pages"), list) else []
    front = str((report.get("site") or {}).get("page_on_front", "")) if isinstance(report.get("site"), dict) else ""
    for pg in pages:
        if pg.get("status") == "publish" and pg.get("link") and pg.get("slug") not in skip and str(pg.get("id")) != front:
            targets.append((f"page_{pg['slug']}", pg["link"]))

    css_seen = {}
    # 记住预览 cookie：页面跳转（例如询价页转到需求单）时跳转后的页面同样按预览身份打开
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def fetch(url):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 aurora-audit"})
        with opener.open(req, timeout=60) as resp:
            return resp.read()

    report["pages_html"] = {}
    for label, url in targets:
        full = url + ("&" if "?" in url else "?") + "aurora_preview=" + key if key else url
        try:
            html = fetch(full).decode("utf-8", "replace")
        except Exception as e:
            report["pages_html"][label] = {"url": url, "error": str(e)[:200]}
            print(f"! 页面 {label}：{e}")
            continue
        files[f"html/{label}.html"] = html.encode("utf-8")
        report["pages_html"][label] = {"url": url, "file": f"html/{label}.html", "bytes": len(html)}
        print(f"✓ 页面 {label}（{len(html) // 1024} KB）")
        for href in re.findall(r"<link[^>]+rel=[\"']stylesheet[\"'][^>]*href=[\"']([^\"']+)", html) + \
                re.findall(r"<link[^>]+href=[\"']([^\"']+)[\"'][^>]*rel=[\"']stylesheet", html):
            href = href.replace("&#038;", "&").replace("&amp;", "&")
            absu = urllib.parse.urljoin(url, href)
            if urllib.parse.urlparse(absu).netloc != host or absu in css_seen:
                continue
            name = "css/" + re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.urlparse(absu).path.strip("/"))[-120:]
            try:
                files[name] = fetch(absu)
                css_seen[absu] = name
            except Exception as e:
                css_seen[absu] = f"error: {e}"
    report["css_map"] = css_seen
    print(f"✓ 样式表 {sum(1 for v in css_seen.values() if v.startswith('css/'))} 个")

    out_path = os.path.expanduser(out_path)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("report.json", json.dumps(report, ensure_ascii=False, indent=2))
        for name, data in files.items():
            z.writestr(name, data)
    print(f"\n✓ 诊断包已保存：{out_path}（{os.path.getsize(out_path) // 1024} KB）")
    print("  把这个文件拖进和 Claude 的对话里。里面没有任何密码。")


RESTORE_SLUGS = ["home", "about", "faq", "wholesale"]


def find_page(wp, slug):
    found, _ = wp.req("GET", "wp/v2/pages", params={"slug": slug, "status": "publish,draft,private",
                                                     "context": "edit", "_fields": "id,slug,status,content"})
    return found[0] if found else None


def cmd_restore_pages(wp, dry_run=False):
    """把 pages 命令改名为「-old」的站点原有页面恢复到原地址，并恢复原首页；
    本脚本建的同名页面改为草稿、地址改成 aurora-xxx（不删除，随时可再启用）。"""
    restored = {}
    for slug in RESTORE_SLUGS:
        old = find_page(wp, f"{slug}-old")
        if not old:
            print(f"· /{slug}-old/ 不存在，跳过")
            continue
        current = find_page(wp, slug)
        if current and PAGE_MARKER not in current["content"]["raw"]:
            print(f"! /{slug}/ 上是另一个不是本脚本建的页面（ID {current['id']}），为安全起见跳过")
            continue
        if dry_run:
            print(f"[dry-run] /{slug}-old/（ID {old['id']}）→ /{slug}/" + (f"；本脚本的页面 ID {current['id']} → 草稿 /aurora-{slug}/" if current else ""))
            continue
        if current:
            wp.req("POST", f"wp/v2/pages/{current['id']}", {"slug": f"aurora-{slug}", "status": "draft"})
        res, _ = wp.req("POST", f"wp/v2/pages/{old['id']}", {"slug": slug})
        if res.get("slug") != slug:
            print(f"! 页面 ID {old['id']} 的地址变成了 /{res.get('slug')}/，请到后台检查")
        else:
            print(f"✓ 已恢复 /{slug}/（ID {old['id']}）" + (f"，本脚本的同名页面改为草稿 /aurora-{slug}/" if current else ""))
        restored[slug] = old["id"]
    if "home" in restored and not dry_run:
        wp.req("POST", "wp/v2/settings", {"show_on_front": "page", "page_on_front": restored["home"]})
        print(f"✓ 网站首页已恢复为原来的页面（ID {restored['home']}）")



DEDUPE_MIN = 0.9


def cmd_dedupe(wp, dry_run=False):
    """标准目录里与站点原有产品同型号的那部分改为草稿（不删除，后台可一键恢复）。
    型号按名称比对：单复数、少写或多写品牌/规格词（BHK、Cabinet）、常见拼写差异都算同一款，数字必须一致。"""
    with open(os.path.join(CONTENT_DIR, "catalog.csv"), newline="", encoding="utf-8") as f:
        ours = {r["SKU"] for r in csv.DictReader(f)}
    products = wp.get_all("wc/v3/products", {"status": "any", "_fields": "id,name,sku,status,meta_data"})
    existing = [(p, name_tokens(p["name"])) for p in products if p.get("sku") not in ours]
    dups = []
    for p in products:
        if p.get("sku") not in ours or p.get("status") != "publish":
            continue
        en = name_tokens(next((m["value"] for m in p.get("meta_data", []) if m["key"] == "aurora_name_en"), ""))
        score, twin = max(((name_score(en, k), q) for q, k in existing), key=lambda x: x[0], default=(0, None))
        if twin and score >= DEDUPE_MIN:
            dups.append((p, twin))
    print(f"标准目录中与原有产品重复的型号：{len(dups)} 款")
    for p, twin in dups:
        print(f"  {p['sku']:<14} {p['name']}  ↔  原有 {twin.get('sku')} {twin['name']}")
    if dry_run or not dups:
        return
    save_products(wp, [{"id": p["id"], "status": "draft"} for p, _ in dups], "改为草稿")
    print(f"✓ 已把 {len(dups)} 款重复型号改为草稿（后台 产品 → 草稿 可恢复）")


def cmd_preview_link(wp):
    data, _ = wp.req("GET", "wp/v2/settings", params={"_fields": "aurora_preview_key"})
    key = (data or {}).get("aurora_preview_key")
    if not key:
        print("! 读不到预览密钥（aurora-core 未启用或版本过旧）")
        return
    print(f"✓ 预览分享链接（内部预览模式下外人用它也能看网站，只发给信任的人）：\n  {wp.site}/?aurora_preview={key}")


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


INSTALLER_NAME = "Aurora 一次性安装器（会自动删除）"


def cmd_cleanup(wp, dry_run=False):
    # 之前 install-plugin 没删掉的临时安装片段
    for sn in wp.get_or_none("code-snippets/v1/snippets") or []:
        if sn.get("name") == INSTALLER_NAME:
            if dry_run:
                print(f"[dry-run] 将删除遗留的临时安装片段 ID {sn['id']}")
                continue
            try:
                wp.delete(f"code-snippets/v1/snippets/{sn['id']}")
            except SystemExit as e:
                # 有的服务器第一次删除其实成功了却返回错误，第二次再删就报「删不掉」：先看它是否还在
                left = next((x for x in wp.get_or_none("code-snippets/v1/snippets") or [] if x["id"] == sn["id"]), None)
                if left:
                    if left.get("active"):
                        wp.req("POST", f"code-snippets/v1/snippets/{sn['id']}", {"active": False})
                    print(f"! 遗留的临时安装片段 ID {sn['id']} 删不掉，已确认是停用状态、不会运行，"
                          f"可以之后到后台 Snippets 里手动删除。（{str(e).splitlines()[0]}）")
                    continue
            print(f"✓ 已删除遗留的临时安装片段 ID {sn['id']}")
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
    ap.add_argument("command", choices=["check", "install-plugin", "configure", "import", "images", "pages", "menu", "cleanup",
                                       "preview-link", "audit", "restore-pages", "dedupe", "photo-inventory", "photo-apply",
                                       "photo-restore", "rename", "merge", "create-drafts", "mark-review",
                                       "all"])
    ap.add_argument("csv", nargs="?", help="产品 CSV 文件（import / all 需要）")
    ap.add_argument("--map", action="append", default=[], metavar="字段=列名",
                    help="手动指定字段映射，例如 --map price=USD售价")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写入网站")
    ap.add_argument("--limit", type=int, help="只导入前 N 行（测试用）")
    ap.add_argument("--photos", metavar="目录", help="images 命令：实拍图目录，文件按 SKU 或产品名命名")
    ap.add_argument("--urls", metavar="CSV", help="images 命令：临时图清单（sku,url 两列）")
    ap.add_argument("--mapping", metavar="CSV", help="photo-apply：核对确认后的照片对照表")
    ap.add_argument("--backup", metavar="JSON", help="photo-restore：产品图片备份文件")
    ap.add_argument("--clear-temp", action="store_true", help="images 命令：把临时图全部换回品牌图")
    ap.add_argument("--out", default="~/Desktop/aurora-audit.zip", help="audit 命令：诊断包保存位置")
    ap.add_argument("--replace-pages", action="store_true", help="pages 命令：同名的站点原有页面改名为 -old 后替换（默认保留不动）")
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
    if args.command in ("install-plugin", "all"):
        cmd_install_plugin(wp, args.dry_run)
    if args.command in ("configure", "all"):
        cmd_configure(wp, args.dry_run)
    if args.command in ("import", "all"):
        cmd_import(wp, args.csv, overrides, args.dry_run, args.limit)
    if args.command in ("images", "all"):
        cmd_images(wp, args.photos, args.urls, args.clear_temp, args.dry_run)
    if args.command in ("pages", "all"):
        cmd_pages(wp, args.dry_run, args.replace_pages)
    if args.command in ("menu", "all"):
        cmd_menu(wp, args.dry_run)
    if args.command == "cleanup":
        cmd_cleanup(wp, args.dry_run)
    if args.command == "audit":
        cmd_audit(wp, args.out)
    if args.command == "restore-pages":
        cmd_restore_pages(wp, args.dry_run)
    if args.command == "dedupe":
        cmd_dedupe(wp, args.dry_run)
    if args.command == "photo-inventory":
        cmd_photo_inventory(wp, args.photos, args.out if args.out != "~/Desktop/aurora-audit.zip"
                            else "~/Desktop/aurora-图片清单.zip")
    if args.command == "photo-apply":
        cmd_photo_apply(wp, args.photos, args.mapping, args.dry_run)
    if args.command == "photo-restore":
        cmd_photo_restore(wp, args.backup)
    if args.command == "rename":
        cmd_rename(wp, args.dry_run)
    if args.command == "merge":
        cmd_merge(wp, args.dry_run)
    if args.command == "create-drafts":
        cmd_create_drafts(wp, args.dry_run)
    if args.command == "mark-review":
        cmd_mark_review(wp, args.dry_run)
    if args.command in ("preview-link", "all") and not args.dry_run:
        cmd_preview_link(wp)


if __name__ == "__main__":
    main()
