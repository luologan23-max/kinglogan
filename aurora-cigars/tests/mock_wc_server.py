"""极简 WooCommerce REST 模拟服务，用来测试 aurora_setup.py 的写入流程。
用法：python3 tests/mock_wc_server.py 8765   （运行后把 AURORA_SITE 指向 http://127.0.0.1:8765）
"""
import base64
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

AUTH = "Basic " + base64.b64encode(b"tester:abcd efgh ijkl").decode()
state = {"products": [], "cats": [], "pages": [], "settings": {}, "next": 100}


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
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or "null")

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
                        state["products"][i] = dict(prod, **item)
                        res["update"].append(state["products"][i])
            return self.send(200, res)
        if p == "wp/v2/pages":
            if method == "GET":
                return self.send(200, [{"id": pg["id"]} for pg in state["pages"] if pg["slug"] == q.get("slug")])
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
            state["settings"].update(body)
            return self.send(200, body)
        if p == "__state":
            return self.send(200, state)
        return self.send(404, {"code": "rest_no_route", "path": p})

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
