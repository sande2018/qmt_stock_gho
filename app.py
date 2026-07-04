# coding:utf-8
"""
app.py - 量化持仓可视化看板
============================
从远程API获取数据，本地转发，不暴露真实数据源地址
仅提供信息查询，不提供任何操作

启动方式:
    python app.py
    手机访问: http://<电脑IP>:5985
"""

import json
import os
import hashlib
import datetime
import requests
from flask import Flask, render_template, jsonify, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = os.urandom(24)

PASSWORDS = {
    "mima123": {
        "允许访问": True,
        "有效期至": "20270601",
        "拒绝提示": "系统维护中",
        "到期提示": "链接已失效",
        "资产查看": False,
        "持仓查看": True,
    }, 
    "mima666": {
        "允许访问": True,
        "有效期至": "20270601",
        "拒绝提示": "系统维护中",
        "到期提示": "链接已失效",
        "资产查看": False,
        "持仓查看": True,
    },
    "mima996": {
        "允许访问": True,
        "有效期至": "20270301",
        "拒绝提示": "系统维护中",
        "到期提示": "链接已失效",
        "资产查看": False,
        "持仓查看": True,
    },
    "mm999": {
        "允许访问": True,
        "有效期至": "20270601",
        "拒绝提示": "系统维护中",
        "到期提示": "链接已失效",
        "资产查看": True,
        "持仓查看": True,
    },
    "mm2026": {
        "允许访问": True,
        "有效期至": "20270601",
        "拒绝提示": "系统维护中",
        "到期提示": "链接已失效",
        "资产查看": True,
        "持仓查看": True,
    },
}

REMOTE_API = "http://你运行api.py的服务器公网IP:43958/api/chaxunData"

SALT_PREFIX = "s_t_o_c_k_"


def _make_key():
    """生成 MD5 密钥: s_t_o_c_k_ + 当前日期 → MD5"""
    today = datetime.date.today().strftime("%Y%m%d")
    raw = SALT_PREFIX + today
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def fetch_remote_data():
    """从远程API获取数据，返回 dict 或 None"""
    url = REMOTE_API + "?key=" + _make_key()
    try:
        resp = requests.get(url, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"[数据获取] 远程API请求失败: {e}")
        return None


def _filter_assets(data):
    """根据当前登录密码的权限，隐藏资产和持仓字段"""
    if not data:
        return data
    pwd = session.get("password")
    if not pwd or pwd not in PASSWORDS:
        return data
    info = PASSWORDS[pwd]
    if not info.get("资产查看", False):
        if "account" in data:
            for key in ("total_assets", "net_asset", "available"):
                data["account"].pop(key, None)
    if not info.get("持仓查看", False):
        data.pop("positions", None)
    return data


def _check_password(pwd):
    """
    校验密码，返回 (通过, 错误提示)
    - 密码不存在 → (False, "密码错误")
    - 不允许访问 → (False, 拒绝提示)
    - 已过期 → (False, 到期提示)
    - 全部通过 → (True, None)
    """
    if pwd not in PASSWORDS:
        return False, "密码错误"
    info = PASSWORDS[pwd]
    if not info["允许访问"]:
        return False, info["拒绝提示"]
    today = datetime.date.today().strftime("%Y%m%d")
    if today > info["有效期至"]:
        return False, info["到期提示"]
    return True, None


def _is_session_valid():
    """检查当前 session 对应的密码是否仍然有效（每次请求都校验）"""
    pwd = session.get("password")
    if not pwd or pwd not in PASSWORDS:
        return False
    info = PASSWORDS[pwd]
    if not info["允许访问"]:
        return False
    today = datetime.date.today().strftime("%Y%m%d")
    if today > info["有效期至"]:
        return False
    return True


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in") or not _is_session_valid():
            session.clear()
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    # 已登录且session有效则直接跳转
    if session.get("logged_in") and _is_session_valid():
        return redirect(url_for("index"))
    if request.method == "POST":
        pwd = request.form.get("password", "")
        ok, msg = _check_password(pwd)
        if ok:
            session["logged_in"] = True
            session["password"] = pwd
            return redirect(url_for("index"))
        return render_template("login.html", error=msg)
    # GET: 检查 URL 参数 ?pwd=xxx 自动登录
    pwd = request.args.get("pwd")
    if pwd:
        ok, msg = _check_password(pwd)
        if ok:
            session["logged_in"] = True
            session["password"] = pwd
            return redirect(url_for("index"))
        return render_template("login.html", error=msg)
    return render_template("login.html", error=None)


@app.route("/")
@login_required
def index():
    data = fetch_remote_data()
    data = _filter_assets(data)
    return render_template("index.html", data=data)


@app.route("/api/data")
@login_required
def api_data():
    data = fetch_remote_data()
    data = _filter_assets(data)
    if data:
        return jsonify(data)
    return jsonify({"error": "no data"}), 404


if __name__ == "__main__":
    print("=" * 50)
    print("  量化持仓看板 已启动")
    print(f"  密码数量: {len(PASSWORDS)} 个")
    for k, v in PASSWORDS.items():
        status = "允许" if v["允许访问"] else "拒绝"
        print(f"    {k} → {status} | 有效期至 {v['有效期至']}")
    print("  本机访问: http://127.0.0.1:5985")
    print("  手机访问: http://<电脑局域网IP>:5985")
    print("  快捷登录: http://<IP>:5985/login?pwd=密码")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5985, debug=False)
