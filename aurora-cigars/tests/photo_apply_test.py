"""按对照表上传实拍图的端到端测试（模拟网站）。python3 tests/photo_apply_test.py
需要 Pillow（生成测试图片、检查横条图补成正方形）。"""
import csv
import io
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)
import aurora_setup as A  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" — {detail}"))
    fails += 0 if ok else 1


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def save_img(path, size, color="saddlebrown", mode="RGB"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new(mode, size, color).save(path)


with tempfile.TemporaryDirectory() as tmp:
    # 横条图补成正方形：宽高、白边、居中
    strip = os.path.join(tmp, "strip.png")
    im = Image.new("RGBA", (900, 130), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (880, 110), "saddlebrown"), (10, 10))
    im.save(strip)
    out, ext = A.prepare_photo(strip)
    with Image.open(out) as o:
        check("横条图转成 JPG", ext == ".jpg" and o.format == "JPEG", (ext, o.format))
        check("横条图补成正方形", o.width == o.height == round(900 * A.PAD), o.size)
        check("补边是白色", o.getpixel((2, 2)) == (255, 255, 255), o.getpixel((2, 2)))
        px = o.getpixel((o.width // 2, (o.height - 130) // 2 + 3))
        check("透明背景铺白", min(px) > 240, px)
        check("雪茄在正中", o.getpixel((o.width // 2, o.height // 2))[0] < 200, o.getpixel((o.width // 2, o.height // 2)))
    # 照片带着「旋转 90°」的方向标记（EXIF 方向 8），像素本身是正的：上传的副本去掉标记，像素不动
    exif = Image.Exif()
    exif[274] = 8
    box = os.path.join(tmp, "box.jpg")
    Image.new("RGB", (1080, 1440), "saddlebrown").save(box, exif=exif.tobytes())
    out2, ext2 = A.prepare_photo(box)
    with Image.open(out2) as o, Image.open(box) as b:
        check("普通照片去掉方向标记", out2 != box and o.getexif().get(274) is None, o.getexif().get(274))
        check("普通照片像素不动、不重新压缩", o.size == (1080, 1440) and o.tobytes() == b.tobytes(), o.size)
    check("原图的方向标记还在（原图不改）", Image.open(box).getexif().get(274) == 8)
    sips_like = os.path.join(tmp, "sips.jpg")  # sips 转出来的 JPG 会带着原图的方向标记
    Image.new("RGB", (1008, 1008), "white").save(sips_like, exif=exif.tobytes())
    A.drop_exif(sips_like)
    with Image.open(sips_like) as o:
        check("转换后的 JPG 也去掉方向标记", o.getexif().get(274) is None and o.size == (1008, 1008), o.getexif())
    os.remove(out)
    check("原图没有改动", Image.open(strip).size == (900, 130))

    # 模拟网站 + 拖进两个文件夹的汇总目录（对照表里只写文件名）
    port = free_port()
    server = subprocess.Popen([sys.executable, os.path.join(HERE, "mock_wc_server.py"), str(port)])
    try:
        site = f"http://127.0.0.1:{port}"
        for _ in range(50):
            try:
                urllib.request.urlopen(site + "/")
                break
            except OSError:
                time.sleep(0.1)
        wp = A.WP(site, "tester", "abcd efgh ijkl")
        brand = {"key": "aurora_image_source", "value": "brand"}
        wp.req("POST", "wc/v3/products/batch", {"create": [
            {"sku": "CUB-023", "name": "Cohiba Siglo I", "status": "publish", "images": [{"id": 9}], "meta_data": [brand]},
            {"sku": "CUB-068", "name": "Partagás Lusitanias", "status": "publish", "images": [{"id": 9}], "meta_data": [brand]},
            {"sku": "CUB-093", "name": "H. Upmann Connoisseur No.2", "status": "publish", "meta_data": [brand]},
            {"sku": "COH-MSG-25", "name": "高希霸 半世纪", "status": "publish", "meta_data": [brand]},
        ]})
        hub = os.path.join(tmp, "hub")
        save_img(os.path.join(hub, "1211", "高希霸 世纪—.PNG"), (900, 140))
        save_img(os.path.join(hub, "1211", "帕特加斯 路西塔尼亚.PNG"), (900, 91))
        save_img(os.path.join(hub, "1211", "帕特加斯 路西塔尼亚2.JPG"), (1080, 1440))
        save_img(os.path.join(hub, "1211", "乌普曼 鉴赏家2号.PNG"), (900, 136))
        save_img(os.path.join(hub, "热门 2", "别的照片.PNG"), (900, 120))
        # 另一个文件夹里有同名照片：一张内容不同（正方形，被选中就会以 PNG 原样上传），一张是一模一样的副本
        save_img(os.path.join(hub, "热门 2", "高希霸 世纪—.PNG"), (600, 600), "navy")
        with open(os.path.join(hub, "1211", "帕特加斯 路西塔尼亚.PNG"), "rb") as src, \
                open(os.path.join(hub, "热门 2", "帕特加斯 路西塔尼亚.PNG"), "wb") as dst:
            dst.write(src.read())
        sha = {"高希霸 世纪—.PNG": A.file_sha1(os.path.join(hub, "1211", "高希霸 世纪—.PNG"))}  # 核对时记下的指纹
        mapping = os.path.join(tmp, "mapping.csv")
        rows = [
            ("高希霸 世纪—.PNG", "CUB-023", "主图", "确认"),
            ("帕特加斯 路西塔尼亚2.JPG", "CUB-068", "包装", "确认"),
            ("帕特加斯 路西塔尼亚.PNG", "CUB-068", "主图", "确认"),
            ("乌普曼 鉴赏家2号.PNG", "CUB-093", "主图", "待确认"),
            ("别的照片.PNG", "", "", "不上传"),
        ]
        with open(mapping, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["file", "sha1", "sku", "product", "role", "order", "status", "note"])
            w.writerows([(fl, sha.get(fl, ""), sku, "", role, 1, st, "") for fl, sku, role, st in rows])

        def state():
            return wp.req("GET", "__state")[0]

        def run():
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                A.cmd_photo_apply(wp, hub, mapping)
            finally:
                sys.stdout = old
            return buf.getvalue()

        home = os.environ.get("HOME")
        os.environ["HOME"] = tmp  # 备份写到临时目录，不写到真的桌面
        os.makedirs(os.path.join(tmp, "Desktop"), exist_ok=True)
        try:
            log = run()
            st = state()
            by_sku = {p["sku"]: p for p in st["products"]}
            media = {m["id"]: m for m in st["media"]}
            names = lambda sku: [media[i["id"]]["slug"] for i in by_sku[sku].get("images", [])]
            check("Siglo I 配到 CUB-023", names("CUB-023") == ["cub-023"], names("CUB-023"))
            check("半世纪没有被配图", by_sku["COH-MSG-25"].get("images") in (None, []), by_sku["COH-MSG-25"].get("images"))
            check("主图在前、包装照进图集", names("CUB-068") == ["cub-068", "cub-068-2"], names("CUB-068"))
            check("待确认的不上传", not by_sku["CUB-093"].get("images"), by_sku["CUB-093"].get("images"))
            check("同名照片按指纹选中核对过的那张（横条图以 JPG 上传）",
                  media[by_sku["CUB-023"]["images"][0]["id"]]["type"] == "image/jpeg", log)
            meta = {m["key"]: m["value"] for m in by_sku["CUB-068"]["meta_data"]}
            check("记下图片来源和文件", meta.get("aurora_image_source") == "photo"
                  and meta.get("aurora_photo_files") == "帕特加斯 路西塔尼亚.PNG|帕特加斯 路西塔尼亚2.JPG", meta)
            check("上传前先备份", any(n.startswith("aurora-产品图片备份-上传前") for n in os.listdir(os.path.join(tmp, "Desktop"))), log)
            uploads = len(st["media"])
            log2 = run()
            check("重新运行不重复上传", len(state()["media"]) == uploads and "之前已配好，跳过" in log2, log2)
            # 旧版处理上传的（没有去掉方向标记，网站把图转歪了）：重新运行时按新方式重传
            pid = by_sku["CUB-023"]["id"]
            wp.req("POST", "wc/v3/products/batch", {"update": [
                {"id": pid, "meta_data": [{"key": "aurora_photo_prep", "value": ""}]}]})
            run()
            st = state()
            redone = next(p for p in st["products"] if p["id"] == pid)
            check("旧版处理的照片会重传", len(st["media"]) == uploads + 1
                  and redone["images"][0]["id"] != by_sku["CUB-023"]["images"][0]["id"], len(st["media"]) - uploads)
            uploads = len(st["media"])

            # 一张图坏了：其他照常上传，报出失败的那款，重跑只补它
            with open(os.path.join(hub, "1211", "乌普曼 鉴赏家2号.PNG"), "wb") as f:
                f.write(b"not an image")
            rows[3] = ("乌普曼 鉴赏家2号.PNG", "CUB-093", "主图", "确认")
            rows.append(("高希霸 世纪—.PNG", "COH-MSG-25", "主图", "确认"))  # 只是为了多一款要处理的产品
            with open(mapping, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["file", "sha1", "sku", "product", "role", "order", "status", "note"])
                w.writerows([(fl, sha.get(fl, ""), sku, "", role, 1, st_, "") for fl, sku, role, st_ in rows])
            orig_upload = A.WP.upload

            def flaky(self, path, filename, alt):
                if filename.startswith("CUB-093"):
                    raise SystemExit("✗ POST wp/v2/media → HTTP 500")
                return orig_upload(self, path, filename, alt)

            A.WP.upload = flaky
            try:
                log3 = run()
            finally:
                A.WP.upload = orig_upload
            by_sku = {p["sku"]: p for p in state()["products"]}
            check("一款失败不影响其他款", bool(by_sku["COH-MSG-25"].get("images")), log3)
            check("报出失败的产品", "CUB-093" in log3 and "没有上传成功" in log3, log3)

            # 没有指纹、同名照片内容又不同：不猜，整批先不上传；指纹对不上也不上传
            def blocked(sha1):
                with open(mapping, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["file", "sha1", "sku", "product", "role", "order", "status", "note"])
                    w.writerow(["高希霸 世纪—.PNG", sha1, "CUB-023", "", "主图", 1, "确认", ""])
                buf = io.StringIO()
                old_out, sys.stdout = sys.stdout, buf
                try:
                    A.cmd_photo_apply(wp, hub, mapping)
                    return False, buf.getvalue()
                except SystemExit:
                    return True, buf.getvalue()
                finally:
                    sys.stdout = old_out
            stopped, out = blocked("")
            check("没有指纹且同名照片不同时不上传", stopped and "内容不同" in out, out)
            stopped, out = blocked("0" * 40)
            check("指纹对不上时不上传", stopped and "和核对时不一样" in out, out)

            # 站上没有的限量款新建为草稿（content/new-products.csv）
            with open(os.path.join(A.CONTENT_DIR, "new-products.csv"), newline="", encoding="utf-8") as f:
                new_rows = list(csv.DictReader(f))
            for slug in ("collection", "punch-collection", "limited-editions"):
                wp.req("POST", "wc/v3/products/categories", {"slug": slug, "name": slug})
            cat_id = {c["slug"]: c["id"] for c in state()["cats"]}
            wp.req("POST", "wc/v3/products/batch", {"create": [  # 已有同名产品的不能再建
                {"sku": "OLD-1", "name": new_rows[0]["name"], "status": "publish"}]})
            buf = io.StringIO()
            old_out, sys.stdout = sys.stdout, buf
            try:
                A.cmd_create_drafts(wp)
                A.cmd_create_drafts(wp)
            finally:
                sys.stdout = old_out
            created = [p for p in state()["products"] if p.get("sku", "").startswith("LTD-")]
            check("新建的都是草稿", created and all(p["status"] == "draft" for p in created), created[:1])
            check("已有同名产品的不新建", new_rows[0]["sku"] not in {p["sku"] for p in created}
                  and "已有同名" in buf.getvalue(), buf.getvalue()[:300])
            check("其余各建一次（重跑不重复）", len(created) == len(new_rows) - 1, len(created))
            punch = next(p for p in created if "潘趣" in p["name"])
            check("分类：Collection + 品牌 + Limited Editions",
                  [c["id"] for c in punch["categories"]] == [cat_id["collection"], cat_id["punch-collection"],
                                                             cat_id["limited-editions"]], punch["categories"])
            check("没有价格", not punch.get("regular_price"), punch.get("regular_price"))

            # 删除被转歪、没有产品在用的旧实拍图；其他图一律不动
            ids = {name: wp.upload(box, name, "旧图") for name in (
                "CUB-023-rotated.jpg", "CUB-068-2-rotated.jpg", "COH-MSG-25-rotated.jpg",  # 应删除
                "CUB-093-rotated.jpg", "CUB-023-1.jpg", "aurora-brand-cohiba.jpg", "IMG_1234-rotated.jpg")}  # 应保留
            by_sku = {p["sku"]: p for p in state()["products"]}
            wp.req("POST", "wc/v3/products/batch", {"update": [  # 还在用的旧图不能删
                {"id": by_sku["CUB-093"]["id"], "images": [{"id": ids["CUB-093-rotated.jpg"]}]}]})
            buf = io.StringIO()
            old_out, sys.stdout = sys.stdout, buf
            try:
                A.cmd_photo_cleanup(wp)
            finally:
                sys.stdout = old_out
            left = {m["id"] for m in state()["media"]}
            gone = {n for n, i in ids.items() if i not in left}
            check("只删除没人用的旧实拍图", gone == {"CUB-023-rotated.jpg", "CUB-068-2-rotated.jpg", "COH-MSG-25-rotated.jpg"},
                  (gone, buf.getvalue()))
            used = {i["id"] for p in state()["products"] for i in p.get("images") or []} - {9}  # 9 是开头预置的假图片编号
            check("产品正在用的图都还在", used <= left, used - left)
        finally:
            if home:
                os.environ["HOME"] = home
    finally:
        server.terminate()
        server.wait()

print("\n全部通过" if not fails else f"\n{fails} 项失败")
sys.exit(1 if fails else 0)
