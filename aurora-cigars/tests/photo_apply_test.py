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
    box = os.path.join(tmp, "box.jpg")
    save_img(box, (1080, 1440))
    check("普通照片原样上传", A.prepare_photo(box) == (box, ".jpg"))
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
            w.writerow(["file", "sku", "product", "role", "order", "status", "note"])
            w.writerows([(fl, sku, "", role, 1, st, "") for fl, sku, role, st in rows])

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
            check("横条图以 JPG 上传", media[by_sku["CUB-023"]["images"][0]["id"]]["type"] == "image/jpeg")
            meta = {m["key"]: m["value"] for m in by_sku["CUB-068"]["meta_data"]}
            check("记下图片来源和文件", meta.get("aurora_image_source") == "photo"
                  and meta.get("aurora_photo_files") == "帕特加斯 路西塔尼亚.PNG|帕特加斯 路西塔尼亚2.JPG", meta)
            check("上传前先备份", any(n.startswith("aurora-产品图片备份-上传前") for n in os.listdir(os.path.join(tmp, "Desktop"))), log)
            uploads = len(st["media"])
            log2 = run()
            check("重新运行不重复上传", len(state()["media"]) == uploads and "之前已配好，跳过" in log2, log2)

            # 一张图坏了：其他照常上传，报出失败的那款，重跑只补它
            with open(os.path.join(hub, "1211", "乌普曼 鉴赏家2号.PNG"), "wb") as f:
                f.write(b"not an image")
            rows[3] = ("乌普曼 鉴赏家2号.PNG", "CUB-093", "主图", "确认")
            rows.append(("高希霸 世纪—.PNG", "COH-MSG-25", "主图", "确认"))  # 只是为了多一款要处理的产品
            with open(mapping, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["file", "sku", "product", "role", "order", "status", "note"])
                w.writerows([(fl, sku, "", role, 1, st_, "") for fl, sku, role, st_ in rows])
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
        finally:
            if home:
                os.environ["HOME"] = home
    finally:
        server.terminate()
        server.wait()

print("\n全部通过" if not fails else f"\n{fails} 项失败")
sys.exit(1 if fails else 0)
