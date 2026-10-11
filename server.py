# -*- coding: utf-8 -*-
"""
易经灵占 · 本地中转服务器
  - 托管 index.html
  - POST /api/divine  {question, hexagramLines:[0/1x6]} -> 调 Gemini 解读，返回 {interpretation, model}
AI 请求由本服务器发出：自动探测 Windows 系统代理（127.0.0.1:10809 等），浏览器无需直连 Google。
启动： python server.py  （默认 http://127.0.0.1:8763）
"""
import json
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8763"))

# 每次请求时重新探测（用户可随时开关代理，无需重启本服务）
def detect_proxy():
    # 1) Windows 注册表（主路径，不受 shell 环境变量干扰）
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as k:
            enabled, _ = winreg.QueryValueEx(k, "ProxyEnable")
            server, _ = winreg.QueryValueEx(k, "ProxyServer")
        if enabled and server:
            if "=" in server:
                for part in server.split(";"):
                    if part.strip().lower().startswith(("https=", "http=")):
                        return "http://" + part.split("=", 1)[1]
                return "http://" + server.split(";")[0]
            return "http://" + server
    except Exception:
        pass
    # 2) 环境变量里显式声明的 http(s)_proxy（NO_PROXY 会让 getproxies() 失真，故单独取）
    import os
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(var)
        if v:
            return v
    # 3) 常见本地代理端口兜底（注册表关了但代理软件还开着的情况）
    import socket
    for port in (10809, 7890, 7897, 1080, 8888):
        s = socket.socket()
        s.settimeout(0.2)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            return "http://127.0.0.1:%d" % port
        except Exception:
            s.close()
    return None

PROXY = detect_proxy()
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}) if PROXY else urllib.request.ProxyHandler({})
)

# 模型降试顺序：lite 稳定快速，主力模型若临时过载(503)则依次回退
MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-flash-latest",
]
TIMEOUT = 45

payload_meta = {}


def build_prompt(question, hexa):
    # 前端已组装好 system prompt（含变爻取辞规则）时优先使用
    meta = payload_meta or {}
    sys_text = meta.get("sys")
    if not sys_text:
        moving = hexa.get("moving") or []
        sys_text = (
            "你是精通《周易》与朱熹《易学启蒙》变占法的断卦师，文风古雅而切中人心。用户起得"
            + hexa["z"] + "卦（第" + str(hexa["n"]) + "卦），卦辞：「" + hexa["g"] + "」。"
            + ("动爻爻辞已附，取断规则：" + (meta.get("rule") or "") if moving else "六爻皆不变，以本卦卦辞断之。")
            + "请用 markdown 输出：卦象总览、动爻详解、之卦展望、行动建议（三条短句），全文 450 字以内，"
              "不要开场白与免责声明，结尾以一句古风短语收束。"
        )
    user_text = question
    return {
        "systemInstruction": {"parts": [{"text": sys_text}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": 0.9},
    }


def call_gemini(key, question, hexa):
    body = json.dumps(build_prompt(question, hexa)).encode("utf-8")
    last_err = None
    for model in MODELS:
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            method="POST",
        )
        try:
            with opener.open(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                return text, model
            last_err = RuntimeError("AI 返回为空")
        except Exception as e:
            last_err = e
            detail = ""
            if isinstance(e, urllib.error.HTTPError):
                try:
                    raw = e.read().decode("utf-8", "replace")
                    detail = json.loads(raw).get("error", {}).get("message", "")[:200]
                except Exception:
                    detail = raw[:200] if 'raw' in dir() else ""
                if "location is not supported" in detail:
                    last_err = RuntimeError(
                        "当前代理出口节点被 Google 识别为不受支持地区（%s）。请在 v2rayN 里换一个节点（美国/日本/新加坡等）再试。"
                        % (PROXY or "直连"))
                if 404 == e.code:
                    continue  # 模型不可用，换下一个
            print("[divine] %s failed: %r %s" % (model, e, detail), flush=True)
    raise last_err or RuntimeError("所有模型均调用失败")


def find_hexagram(bin_str, moving=None):
    hx = os.path.join(HERE, "hexagrams2.min.json")
    with open(hx, encoding="utf-8") as f:
        arr = json.load(f)
    for h in arr:
        if h["b"] == bin_str:
            h = dict(h)
            h["moving"] = moving or []
            return h
    return dict(arr[0], moving=moving or [])


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.address_string(), fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
                self._send(200, f.read().encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/healthz":
            self._send(200, json.dumps({"ok": True, "proxy": PROXY}).encode("utf-8"))
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        if self.path.split("?")[0] != "/api/divine":
            self._send(404, b'{"error":"not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send(400, json.dumps({"error": "请求体解析失败"}).encode("utf-8"))
            return

        key = (payload.get("apiKey") or "").strip()
        if not key:
            self._send(400, json.dumps({"error": "缺少 API Key，请点击右上角「AI 玄机」设置。"}).encode("utf-8"))
            return

        lines = payload.get("hexagramLines") or []
        # 兼容两种协议：0/1 静态爻（旧）与 6-9 爻值（三枚铜钱法）
        if len(lines) == 6 and all(x in (0, 1) for x in lines):
            vals = [7 if x == 1 else 8 for x in lines]
        elif len(lines) == 6 and all(x in (6, 7, 8, 9) for x in lines):
            vals = [int(x) for x in lines]
        else:
            self._send(400, json.dumps({"error": "卦象数据不合法"}).encode("utf-8"))
            return
        question = str(payload.get("question") or "")[:1500]
        global payload_meta
        payload_meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}

        moving = payload.get("moving")
        if moving is None:
            moving = [i + 1 for i, v in enumerate(vals) if v in (6, 9)]
        moving = [int(p) for p in moving if 1 <= int(p) <= 6]
        static_lines = [1 if v in (7, 9) else 0 for v in vals]
        hexa = find_hexagram("".join(str(x) for x in static_lines), moving)
        hexa["vals"] = vals
        global opener, PROXY
        proxy_now = detect_proxy()
        if proxy_now != PROXY:
            print("[proxy] switched: %r -> %r" % (PROXY, proxy_now))
            PROXY = proxy_now
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}) if PROXY else urllib.request.ProxyHandler({})
            )
        print("[divine] question=%r hexagram=%s(%s) proxy=%s" % (question, hexa["z"], hexa["n"], PROXY or "直连"))
        try:
            text, model = call_gemini(key, question, hexa)
            self._send(200, json.dumps({"interpretation": text, "model": model}, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            msg = "AI 玄机未达：" + re.sub(r"\s+", " ", str(e))[:180]
            self._send(502, json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    print("易经灵占 · 本地中转服务器")
    print("  页面:   http://127.0.0.1:%d/" % PORT)
    print("  AI代理: %s" % (PROXY or "直连（未检测到系统代理）"))
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
