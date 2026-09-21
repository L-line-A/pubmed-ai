# -*- coding: utf-8 -*-
"""PubMed AI 检索 · 公共配置模块（主程序与配置程序共用）"""

import os, sys, shutil, configparser

DEFAULT_API_BASE = "https://api.deepseek.com"
GITHUB_URL = "https://github.com/L-line-A/pubmed-ai"

TEMPLATE = """# ============================================
#  PubMed AI 检索 —— 配置文件
#  建议用「配置设置.exe」修改，不要手动编辑。
# ============================================

[auth]
email = your_email@example.com
deepseek_api_key = sk-这里填你的key

[deepseek]
api_base = https://api.deepseek.com
model = deepseek-chat

[search]
max_results = 30
summary_limit = 500
sort = relevance
download_fulltext = true
confirm_query = true

[output]
output_dir =

[ncbi]
ncbi_api_key =
"""


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def config_dir():
    """配置目录：用户主目录下的 .pubmed-ai（放这里可防止随 exe 一起被分享而泄露 Key）"""
    return os.path.join(os.path.expanduser("~"), ".pubmed-ai")


def cfg_path():
    """配置文件路径：位于用户目录，而非程序同目录"""
    d = config_dir()
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "config.ini")


def default_config():
    return {
        "email": "",
        "deepseek_api_key": "",
        "api_base": DEFAULT_API_BASE,
        "model": "deepseek-chat",
        "max_results": 30,
        "summary_limit": 500,
        "sort": "relevance",
        "download_fulltext": True,
        "confirm_query": True,
        "output_dir": "",
        "ncbi_api_key": "",
    }


def load_config():
    """读配置。无文件则生成模板并返回 None；解析失败也返回 None。"""
    path = cfg_path()
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(TEMPLATE)
        return None
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8-sig")

    def g(section, option, fallback=""):
        try:
            return cp.get(section, option).strip()
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    def to_bool(v):
        return v.lower() in ("true", "yes", "1", "on")

    try:
        return {
            "email": g("auth", "email"),
            "deepseek_api_key": g("auth", "deepseek_api_key"),
            "api_base": g("deepseek", "api_base", DEFAULT_API_BASE) or DEFAULT_API_BASE,
            "model": g("deepseek", "model", "deepseek-chat") or "deepseek-chat",
            "max_results": int(g("search", "max_results", "30") or 30),
            "summary_limit": int(g("search", "summary_limit", "500") or 500),
            "sort": g("search", "sort", "relevance") or "relevance",
            "download_fulltext": to_bool(g("search", "download_fulltext", "true") or "true"),
            "confirm_query": to_bool(g("search", "confirm_query", "true") or "true"),
            "output_dir": g("output", "output_dir"),
            "ncbi_api_key": g("ncbi", "ncbi_api_key"),
        }
    except Exception:
        return None


def save_config(cfg):
    """规范化写回，写前自动备份旧文件为 config.ini.bak"""
    path = cfg_path()
    if os.path.exists(path):
        shutil.copy(path, path + ".bak")
    cp = configparser.ConfigParser()
    cp["auth"] = {
        "email": cfg.get("email", ""),
        "deepseek_api_key": cfg.get("deepseek_api_key", ""),
    }
    cp["deepseek"] = {
        "api_base": cfg.get("api_base", DEFAULT_API_BASE),
        "model": cfg.get("model", "deepseek-chat"),
    }
    cp["search"] = {
        "max_results": str(cfg.get("max_results", 30)),
        "summary_limit": str(cfg.get("summary_limit", 500)),
        "sort": cfg.get("sort", "relevance"),
        "download_fulltext": "true" if cfg.get("download_fulltext", True) else "false",
        "confirm_query": "true" if cfg.get("confirm_query", True) else "false",
    }
    cp["output"] = {"output_dir": cfg.get("output_dir", "")}
    cp["ncbi"] = {"ncbi_api_key": cfg.get("ncbi_api_key", "")}
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)
    return path


# ---------------- 校验器：返回错误信息字符串，None 表示通过 ----------------
def validate_email(v):
    v = v.strip()
    if not v or "@" not in v or "." not in v.split("@")[-1]:
        return "邮箱格式不对，需包含 @ 和点"
    return None


def validate_key(v):
    v = v.strip()
    if not v or not v.lower().startswith("sk-"):
        return "DeepSeek Key 必须以 sk- 开头"
    return None


def validate_url(v):
    v = v.strip()
    if not (v.startswith("http://") or v.startswith("https://")):
        return "地址必须以 http:// 或 https:// 开头"
    return None


def validate_model(v):
    if not v.strip():
        return "模型名不能为空"
    return None


def validate_int_range(v, lo, hi):
    try:
        n = int(v.strip())
        if lo <= n <= hi:
            return None
    except ValueError:
        pass
    return f"必须是 {lo}~{hi} 的整数"


def validate_bool(v):
    if v.strip().lower() in ("y", "n", "true", "false", "1", "0", "yes", "no"):
        return None
    return "只接受 y / n"


def validate_sort(v):
    if v.strip().lower() in ("relevance", "date", "pub_date"):
        return None
    return "只接受 relevance 或 date"


def validate_output_dir(v):
    v = v.strip()
    if not v:
        return None
    if not os.path.isabs(v):
        return "请填绝对路径（如 D:\\结果），或留空"
    return None


def validate_ncbi_key(v):
    v = v.strip()
    if v and " " in v:
        return "不能包含空格"
    return None


def print_banner(title):
    print("=" * 52)
    print(f"   {title}")
    print("=" * 52)
    print("   完全开源免费 · 源码 / 最新版：")
    print(f"   {GITHUB_URL}")
    print("   如被收费请勿购买，直接到上方地址免费获取")
    print("-" * 52)
