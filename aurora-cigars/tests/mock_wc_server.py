"""极简 WooCommerce REST 模拟服务，用来测试 aurora_setup.py 的写入流程。
用法：python3 tests/mock_wc_server.py 8765   （运行后把 AURORA_SITE 指向 http://127.0.0.1:8765）
"""
import base64
import io
import re
import zipfile
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

AUTH = "Basic " + base64.b64encode(b"tester:abcd efgh ijkl").decode()
state = {"products": [], "cats": [], "settings": {"show_on_front": "page", "page_on_front": 7}, "menus": [], "menu_items": [], "media": [], "snippets": {}, "next": 100,
         # 预置一个用户自己做的首页，用来测试「不覆盖」逻辑
         "pages": [{"id": 7, "slug": "home", "title": "Home", "content": "<p>用户原有首页</p>", "status": "publish"}],
         "plugins": [{"plugin": "yith-woocommerce-wishlist/init", "name": "YITH Wishlist", "status": "active"},
                     {"plugin": "yith-woocommerce-request-a-quote/init", "name": "YITH Request a Quote", "status": "active"},
                     {"plugin": "elementor/elementor", "name": "Elementor", "status": "active"}]}


def new_id():
    state["next"] += 1
    return state["next"]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, total_pages=1):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-WP-TotalPages", str(total_pages))
        self.end_headers()
        self.wfile.write(data)

    def route(self, method):
        if self.headers.get("Authorization") != AUTH:
            return self.send(401, {"code": "invalid_username"})
        u = urlparse(self.path)
        p = u.path.replace("/wp-json/", "")
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if method == "DELETE" and os.environ.get("MOCK_BLOCK_DELETE"):  # 模拟服务器拦截 DELETE 方法
            return self.send(405, {"code": "method_not_allowed"})
        method = q.get("_method", method)  # WordPress 的方法覆盖：POST + _method=DELETE
        if p == "wp/v2/media" and method == "POST":
            disp = self.headers.get("Content-Disposition", "")
            name = disp.split('filename="')[1].rstrip('"')
            m = {"id": new_id(), "slug": name.rsplit(".", 1)[0].lower(), "bytes": len(raw), "type": self.headers.get("Content-Type")}
            state["media"].append(m)
            return self.send(201, m)
        body = json.loads(raw or "null")
        if p == "wp/v2/media":
            hits = [m for m in state["media"] if q.get("search", "") in m["slug"]]
            return self.send(200, hits)
        if p.startswith("wp/v2/media/"):
            mid = int(p.rsplit("/", 1)[1])
            for m in state["media"]:
                if m["id"] == mid:
                    m.update(body)
                    return self.send(200, m)

        if p == "wp/v2/users/me":
            return self.send(200, {"name": "Tester", "username": "tester", "roles": ["administrator"]})
        if p == "wc/v3/system_status":
            return self.send(200, {"environment": {"version": "9.9", "wp_version": "6.8"},
                                   "active_plugins": [{"plugin": "woocommerce/woocommerce.php"}, {"plugin": "aurora-core/aurora-core.php"}]})
        if p.startswith("wc/v3/settings/") and p.endswith("/batch"):
            for u_ in body["update"]:
                state["settings"][u_["id"]] = u_["value"]
            return self.send(200, {"update": body["update"]})
        if p == "wc/v3/products/categories":
            if method == "GET":
                page, per = int(q.get("page", 1)), int(q.get("per_page", 10))
                return self.send(200, state["cats"][(page - 1) * per: page * per], max(1, -(-len(state["cats"]) // per)))
            c = dict(body, id=new_id())
            state["cats"].append(c)
            return self.send(201, c)
        if p.startswith("wc/v3/products/categories/"):
            cid = int(p.rsplit("/", 1)[1])
            for c in state["cats"]:
                if c["id"] == cid:
                    c.update(body)
                    return self.send(200, c)
        if p == "wp/v2/menus":
            if method == "GET":
                return self.send(200, state["menus"])
            mnu = dict(body, id=new_id())
            state["menus"].append(mnu)
            return self.send(201, mnu)
        if p == "wp/v2/menu-items":
            state["menu_items"].append(body)
            return self.send(201, dict(body, id=new_id()))
        # Code Snippets REST 接口（简化）
        if p == "code-snippets/v1/snippets":
            if method == "GET":
                return self.send(200, list(state["snippets"].values()))
            sn = dict(body, id=new_id())
            state["snippets"][sn["id"]] = sn
            return self.send(201, sn)
        m = re.fullmatch(r"code-snippets/v1/snippets/(\d+)", p)
        if m:
            sid = int(m.group(1))
            if sid not in state["snippets"]:
                return self.send(404, {"code": "not_found"})
            if method == "DELETE":
                if os.environ.get("MOCK_STUCK_DELETE") and "leftover" in state["snippets"][sid]["code"]:
                    return self.send(500, {"code": "rest_cannot_delete", "message": "The snippet could not be deleted."})
                return self.send(200, state["snippets"].pop(sid))
            state["snippets"][sid].update(body)
            return self.send(200, state["snippets"][sid])
        # 安装片段注册的路由：只有存在已启用的安装片段时才可用，并校验其中的 zip 确实含有插件
        if p == "aurora-install/v1/run":
            sn = next((x for x in state["snippets"].values() if x.get("active") and "aurora-install/v1" in x["code"]), None)
            if not sn:
                return self.send(404, {"code": "rest_no_route"})
            b64 = re.search(r"base64_decode\( '([A-Za-z0-9+/=]+)' \)", sn["code"]).group(1)
            names = zipfile.ZipFile(io.BytesIO(base64.b64decode(b64))).namelist()
            if "aurora-core/aurora-core.php" not in names:
                return self.send(500, {"code": "bad_zip", "names": names})
            state["plugins"] = [x for x in state["plugins"] if x["plugin"] != "aurora-core/aurora-core"]
            state["plugins"].append({"plugin": "aurora-core/aurora-core", "name": "Aurora Core", "status": "active", "version": re.search(r"Version: (\S+)", zipfile.ZipFile(io.BytesIO(base64.b64decode(b64))).read("aurora-core/aurora-core.php").decode()).group(1)})
            return self.send(200, {"installed": True, "active": True})
        if p == "wp/v2/plugins":
            return self.send(200, state["plugins"])
        if p.startswith("wp/v2/plugins/"):
            for pl in state["plugins"]:
                if pl["plugin"] == p[len("wp/v2/plugins/"):]:
                    pl.update(body or {})
                    return self.send(200, pl)
            return self.send(404, {"code": "rest_plugin_not_found"})
        if p == "wc/v3/products":
            page, per = int(q.get("page", 1)), int(q.get("per_page", 10))
            return self.send(200, state["products"][(page - 1) * per: page * per], max(1, -(-len(state["products"]) // per)))
        if p == "wc/v3/products/batch":
            res = {"create": [], "update": []}
            for item in body.get("create", []):
                if not item.get("regular_price") and not item.get("name"):
                    res["create"].append({"id": 0, "error": {"message": "bad"}})
                    continue
                item = dict(item, id=new_id())
                state["products"].append(item)
                res["create"].append(item)
            for item in body.get("update", []):
                for i, prod in enumerate(state["products"]):
                    if prod["id"] == item["id"]:
                        # 与 WooCommerce 一致：meta_data 按 key 合并，不整体覆盖
                        meta = {m["key"]: m for m in prod.get("meta_data", [])}
                        meta.update({m["key"]: m for m in item.get("meta_data", [])})
                        state["products"][i] = dict(prod, **dict(item, meta_data=list(meta.values())))
                        res["update"].append(state["products"][i])
            return self.send(200, res)
        if p == "wp/v2/pages":
            if method == "GET":
                hits = [pg for pg in state["pages"] if pg["slug"] == q.get("slug")] if "slug" in q else state["pages"]
                host = f"http://{self.headers.get('Host')}"
                return self.send(200, [dict(pg, content={"raw": pg["content"]}, link=f"{host}/{pg['slug']}/") for pg in hits])
            pg = dict(body, id=new_id())
            state["pages"].append(pg)
            return self.send(201, pg)
        if p.startswith("wp/v2/pages/"):
            pid = int(p.rsplit("/", 1)[1])
            for pg in state["pages"]:
                if pg["id"] == pid:
                    pg.update(body)
                    return self.send(200, pg)
        if p == "wp/v2/settings":
            if method == "GET":
                return self.send(200, {k: state["settings"].get(k) for k in ("show_on_front", "page_on_front")}
                                 | {"aurora_preview_key": "mockkey123"})
            state["settings"].update(body)
            return self.send(200, body)
        if p == "__state":
            return self.send(200, state)
        return self.send(404, {"code": "rest_no_route", "path": p})

    def do_GET(self):
        # 简易前台：首页链接一个同站样式表和一个外站样式表（外站的不应下载）
        if not self.path.startswith("/wp-json/"):
            path = urlparse(self.path).path
            if os.environ.get("MOCK_PRIVATE") and not path.endswith(".css"):
                # 模拟内部预览模式 + 服务器缓存不回传 Set-Cookie：没带密钥的请求一律是「即将上线」的 503 页面
                if "aurora_preview=mockkey123" not in self.path:
                    body = "<html><body><p>网站即将上线</p></body></html>".encode()
                    self.send_response(503)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if path == "/request-quote/":  # 询价页转到需求单
                    self.send_response(302)
                    self.send_header("Location", f"http://{self.headers.get('Host')}/my-request/")
                    self.end_headers()
                    return
            if path.endswith(".css"):
                body, ctype = b"body{color:#123}", "text/css"
            else:
                body = (b'<html><head><link rel="stylesheet" href="/wp-content/themes/astra/style.css?ver=1">'
                        b'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jost">'
                        b'</head><body class="mock">' + path.encode() + b"</body></html>")
                ctype = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)
            return
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_DELETE(self):
        self.route("DELETE")


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
