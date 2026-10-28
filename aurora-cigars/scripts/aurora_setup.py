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
import json
import os
import re
import sys
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
                "ours": p.get("sku") in ours,
                "meta": {m["key"]: m["value"] for m in p.get("meta_data", [])
                         if isinstance(m.get("value"), (str, int, float)) and not m["key"].startswith("_")},
            } for p in rows],
        }
    section("products", products)

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

    css_seen = {}

    def fetch(url):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 aurora-audit"})
        with urllib.request.urlopen(req, timeout=60) as resp:
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


def model_key(name):
    """型号比对用：去重音、统一 No. 写法，只保留字母数字。"""
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().replace("no.", "no ")
    return re.sub(r"[^a-z0-9]+", "", s)


def cmd_dedupe(wp, dry_run=False):
    """标准目录里与站点原有产品同型号的那部分改为草稿（不删除，后台可一键恢复）。"""
    with open(os.path.join(CONTENT_DIR, "catalog.csv"), newline="", encoding="utf-8") as f:
        ours = {r["SKU"] for r in csv.DictReader(f)}
    products = wp.get_all("wc/v3/products", {"status": "any", "_fields": "id,name,sku,status,meta_data"})
    existing = {model_key(p["name"]): p for p in products if p.get("sku") not in ours}
    dups = []
    for p in products:
        if p.get("sku") not in ours or p.get("status") != "publish":
            continue
        en = next((m["value"] for m in p.get("meta_data", []) if m["key"] == "aurora_name_en"), "")
        twin = existing.get(model_key(en))
        if twin:
            dups.append((p, twin))
    print(f"标准目录中与原有产品重复的型号：{len(dups)} 款")
    for p, twin in dups:
        print(f"  {p['sku']:<14} {p['name']}  ↔  原有 {twin.get('sku')} {twin['name']}")
    if dry_run or not dups:
        return
    for i in range(0, len(dups), 50):
        wp.req("POST", "wc/v3/products/batch", {"update": [{"id": p["id"], "status": "draft"} for p, _ in dups[i:i + 50]]})
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
            wp.delete(f"code-snippets/v1/snippets/{sn['id']}")
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
                                       "preview-link", "audit", "restore-pages", "dedupe", "all"])
    ap.add_argument("csv", nargs="?", help="产品 CSV 文件（import / all 需要）")
    ap.add_argument("--map", action="append", default=[], metavar="字段=列名",
                    help="手动指定字段映射，例如 --map price=USD售价")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写入网站")
    ap.add_argument("--limit", type=int, help="只导入前 N 行（测试用）")
    ap.add_argument("--photos", metavar="目录", help="images 命令：实拍图目录，文件按 SKU 命名")
    ap.add_argument("--urls", metavar="CSV", help="images 命令：临时图清单（sku,url 两列）")
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
    if args.command in ("preview-link", "all") and not args.dry_run:
        cmd_preview_link(wp)


if __name__ == "__main__":
    main()
