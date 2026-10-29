"""换 WhatsApp 号码的测试（模拟网站）：插件设置、启用的代码片段、页面、产品描述一次换掉，停用片段和别的数字不动。
python3 tests/whatsapp_test.py"""
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import aurora_setup as A  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" — {detail}"))
    fails += 0 if ok else 1


def quiet(fn, *a):
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        fn(*a)
        return buf.getvalue(), None
    except SystemExit as e:
        return buf.getvalue(), str(e)
    finally:
        sys.stdout = old


with socket.socket() as sk:
    sk.bind(("127.0.0.1", 0))
    port = sk.getsockname()[1]
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
    nav = "<a href='https://wa.me/971585598868'>WA</a> 订单号 1971585598868 不是电话"
    card = "const WA_NUMBER = '971585598868'; // +971 58 559 8868"
    for name, code, active in (("Global Nav", nav, True), ("Request List JS", card, True), ("Old Footer", nav, False)):
        wp.req("POST", "code-snippets/v1/snippets", {"name": name, "code": code, "active": active})
    wp.req("POST", "wp/v2/pages", {"slug": "contact", "title": "Contact", "status": "publish",
                                   "content": "<p>WhatsApp：+971 585 598 868</p><p>Tel 04 123 4567</p>"})
    wp.req("POST", "wc/v3/products/batch", {"create": [
        {"sku": "CUB-001", "name": "A", "description": "询价请 WhatsApp +971 58 559 8868", "short_description": ""},
        {"sku": "CUB-002", "name": "B", "description": "没有号码", "short_description": ""}]})

    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "Desktop"))
        home, os.environ["HOME"] = os.environ.get("HOME"), tmp
        try:
            out, err = quiet(A.cmd_whatsapp, wp, "0971 58571167")
            check("位数不对的号码不换", err and "9 位" in err and wp.req("GET", "__state")[0]["settings"].get("aurora_whatsapp") is None, err)
            out, err = quiet(A.cmd_whatsapp, wp, "+971 58 571 1167", True)
            st = wp.req("GET", "__state")[0]
            before = {sn["name"]: sn for sn in st["snippets"].values()}
            check("预览只列出不修改", not err and "代码片段" in out and "971585598868" in before["Global Nav"]["code"]
                  and st["settings"].get("aurora_whatsapp") is None, out)
            out, err = quiet(A.cmd_whatsapp, wp, "+971 58 571 1167")
            st = wp.req("GET", "__state")[0]
            snips = {sn["name"]: sn for sn in st["snippets"].values()}
            check("插件设置换成新号码", st["settings"].get("aurora_whatsapp") == "971585711167", st["settings"])
            check("导航片段里的链接换成新号码", "wa.me/971585711167'" in snips["Global Nav"]["code"], snips["Global Nav"]["code"])
            check("别的数字（订单号）不动", "1971585598868" in snips["Global Nav"]["code"])
            check("脚本变量和注释里的号码都换了", snips["Request List JS"]["code"] == "const WA_NUMBER = '971585711167'; // +971 58 571 1167",
                  snips["Request List JS"]["code"])
            check("停用的片段不动", "971585598868" in snips["Old Footer"]["code"])
            page = next(pg for pg in st["pages"] if pg["slug"] == "contact")
            check("页面上的号码换成新号码、其他电话不动", page["content"] == "<p>WhatsApp：+971 58 571 1167</p><p>Tel 04 123 4567</p>", page["content"])
            prods = {p_["sku"]: p_ for p_ in st["products"]}
            check("产品描述里的号码换了", prods["CUB-001"]["description"] == "询价请 WhatsApp +971 58 571 1167", prods["CUB-001"]["description"])
            backups = [n for n in os.listdir(os.path.join(tmp, "Desktop")) if n.startswith("aurora-换号备份")]
            data = json.load(open(os.path.join(tmp, "Desktop", backups[0]), encoding="utf-8")) if backups else {}
            check("换号前先备份原内容", len(backups) == 1 and "971585598868" in json.dumps(data), backups)
            out, err = quiet(A.cmd_whatsapp, wp, "+971 58 571 1167")
            check("重复运行不再改动", "已经全部是新号码" in out, out)
        finally:
            os.environ["HOME"] = home
finally:
    server.terminate()
    server.wait()

print("\n全部通过" if not fails else f"\n{fails} 项失败")
sys.exit(1 if fails else 0)
