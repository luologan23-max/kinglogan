"""把逐张看图后的判断（decisions.json）生成上传用的对照表 content/photo-mapping.csv。
用法：python3 make_mapping.py <清点包目录> <decisions.json> <输出 csv> [--new-products content/new-products.csv]

decisions.json：键是清点编号（manifest 的 no），值是这张照片的判断，例如
  {"164": {"sku": "CUB-021", "role": "主图", "status": "确认", "note": "世纪三 = Siglo III"},
   "100": {"sku": "CUB-068", "role": "包装", "status": "确认", "note": "整盒照片，进图集"},
   "137": {"sku": "RYJ-PJU-25", "role": "主图", "status": "确认", "note": "推断：朱丽叶 = Petit Julietas；比例一致"},
   "43":  {"sku": "", "status": "待确认", "note": "认不出型号"}}
- status：确认（会上传）/ 待确认（不传，等用户）/ 不上传。推断出来的写「确认」，note 以「推断：」开头，审查页会单独列出来请用户核对。
- role：主图 / 包装 / 本体 / 细节 / 其他；一款产品只能有一张主图，其余按 role、order 进图集。
- 没写判断的照片：内容和前面某张完全相同的标「不上传（重复）」，其余标「不上传（站上没有这款产品）」。
- 每行都带清点时的 sha1：上传时按它认出核对过的那一张，几个文件夹里有同名照片也不会传错。
产品名称取清点包 products.json 里的当前名称；新建草稿（--new-products 里的 SKU）取那张表里的名称。"""
import argparse
import csv
import json
import os
import sys

ROLES = {"主图", "包装", "本体", "细节", "其他"}
STATUSES = {"确认", "待确认", "不上传"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("decisions")
    ap.add_argument("out")
    ap.add_argument("--new-products", default="")
    a = ap.parse_args()
    manifest = list(csv.DictReader(open(os.path.join(a.inventory, "manifest.csv"), encoding="utf-8-sig")))
    names = {p["sku"]: " ".join(p["name"].split())
             for p in json.load(open(os.path.join(a.inventory, "products.json"), encoding="utf-8")) if p.get("sku")}
    if a.new_products:
        for r in csv.DictReader(open(a.new_products, encoding="utf-8", newline="")):
            names.setdefault(r["sku"], r["name"])
    decisions = {int(k): v for k, v in json.load(open(a.decisions, encoding="utf-8")).items()}
    errors, mains, rows = [], {}, []
    for m in manifest:
        n = int(m["no"])
        file = f"{m['folder']}/{m['file']}" if m.get("folder") else m["file"]
        d = decisions.get(n)
        if d is None:
            note = f"与「{m['duplicate_of']}」内容完全相同" if m.get("duplicate_of") else "站上没有这款产品"
            rows.append(dict(no=n, file=file, sha1=m["sha1"], sku="", product="", role="", order="", status="不上传", note=note))
            continue
        sku, status, role = d.get("sku", "").strip(), d.get("status", "确认"), d.get("role", "主图" if d.get("sku") else "")
        if status not in STATUSES:
            errors.append(f"#{n}：status 只能是 {'/'.join(STATUSES)}")
        if status == "确认":
            if sku not in names:
                errors.append(f"#{n}：网站和新建草稿表里都没有 SKU {sku}")
            if role not in ROLES:
                errors.append(f"#{n}：role 只能是 {'/'.join(ROLES)}")
            if role == "主图":
                if sku in mains:
                    errors.append(f"#{n}：{sku} 已经有主图 #{mains[sku]}，第二张请用 包装/本体/细节/其他")
                mains[sku] = n
            if m.get("duplicate_of"):
                errors.append(f"#{n}：和「{m['duplicate_of']}」内容完全相同，只上传一张")
        rows.append(dict(no=n, file=file, sha1=m["sha1"], sku=sku, product=names.get(sku, ""), role=role if status == "确认" else "",
                         order=d.get("order", 1) if status == "确认" else "", status=status, note=d.get("note", "")))
    unknown = set(decisions) - {int(m["no"]) for m in manifest}
    if unknown:
        errors.append(f"清点包里没有这些编号：{sorted(unknown)}")
    if errors:
        print("\n".join("✗ " + e for e in errors))
        sys.exit(1)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["no", "file", "sha1", "sku", "product", "role", "order", "status", "note"])
        w.writeheader()
        w.writerows(rows)
    count = lambda s: sum(1 for r in rows if r["status"] == s)
    print(f"✓ {a.out}：确认 {count('确认')} 张（{len({r['sku'] for r in rows if r['status'] == '确认'})} 款产品，"
          f"其中推断 {sum(1 for r in rows if r['status'] == '确认' and r['note'].startswith('推断'))} 张），"
          f"待确认 {count('待确认')} 张，不上传 {count('不上传')} 张")


if __name__ == "__main__":
    main()
