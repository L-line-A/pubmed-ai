#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PubMed AI 文献检索（独立版）
用 DeepSeek 把中文主题转成 PubMed 检索式，再自动检索、抓摘要、下载 OA 全文，
并生成引用格式 / BibTeX / RIS / HTML 汇总页。

配置文件由「配置设置.exe」维护，本程序只读取。
"""
import os, sys, time, csv, json, re, html
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
import config_common as cc

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


# ---------------- DeepSeek 生成检索式 ----------------
SYSTEM_PROMPT = (
    "你是 PubMed 检索专家。用户会给你一个中文或英文的研究主题，请把它转换成一个标准、稳定、可复现的 PubMed 检索式。\n"
    "【构造原则，必须严格遵守】\n"
    "1. 用 PICO 思路把主题拆成若干概念（如疾病、干预/药物、结局等）。\n"
    "2. 每个概念 = 该概念的 MeSH 主题词 + 常见同义词/缩写/英美拼写，用 OR 连接，并用半角括号 () 括起来。\n"
    "3. 每个词必须带字段标签：标准 MeSH 词用 [mh]，自由词/关键词用 [tiab]（标题+摘要）。MeSH 词要准确；不确定某概念的标准 MeSH 词时，就只用自由词 [tiab]，不要编造 MeSH 词。\n"
    "4. 不同概念之间用大写 AND 连接；不要使用 NOT。\n"
    "5. 文献类型限制用 [pt]（如 review[pt]），年份限制用 [dp]（如 2021:2026[dp]），都放在检索式末尾；用户没提就不要加。\n"
    "6. 每个概念只保留最标准、最常用的 1-3 个表述，不要随意增减同义词，保证同样主题生成的检索式一致。\n"
    "【输出格式】\n"
    "只输出一个 JSON，格式严格为：{\"query\":\"检索式\",\"explain\":\"一句中文说明这个检索式查的是什么\"}，不要输出任何其他文字、解释或代码块标记。\n"
    "【示例】\n"
    "输入：2型糖尿病的中医治疗，只要近5年的综述\n"
    "输出：{\"query\":\"(diabetes mellitus type 2[mh] OR type 2 diabetes[tiab] OR T2DM[tiab]) AND (medicine chinese traditional[mh] OR traditional chinese medicine[tiab] OR acupuncture[tiab]) AND review[pt] AND 2021:2026[dp]\",\"explain\":\"检索近5年关于2型糖尿病中医治疗的综述\"}"
)


def gen_query(topic, cfg):
    """返回 (检索式, 中文解释)"""
    url = cfg["api_base"].rstrip("/") + "/chat/completions"
    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": topic},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + cfg["deepseek_api_key"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode("utf-8"))
    content = resp["choices"][0]["message"]["content"].strip()
    m = re.search(r'\{.*\}', content, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            q = obj.get("query", "").strip()
            e = obj.get("explain", "").strip()
            if q:
                return q, e
        except Exception:
            pass
    return content, ""


# ---------------- E-utilities 检索 ----------------
def _get(path, params, email, api_key, retries=3, timeout=90):
    p = dict(params)
    p.setdefault("db", "pubmed")
    p.setdefault("tool", "pubmed-ai")
    p.setdefault("email", email)
    if api_key:
        p.setdefault("api_key", api_key)
    url = EUTILS + path + "?" + urllib.parse.urlencode(p)
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def _parse_xml(data):
    return ET.fromstring(re.sub(rb'<!DOCTYPE[^>]*>', b'', data))


def _local(tag):
    return tag.split('}')[-1]


def _find_local(elem, name):
    if elem is None:
        return None
    for e in elem.iter():
        if _local(e.tag) == name:
            return e
    return None


def esearch(query, retmax, email, api_key, sort="relevance"):
    d = json.loads(_get("esearch.fcgi", {
        "term": query, "retmax": retmax, "sort": sort, "retmode": "json"}, email, api_key).decode("utf-8"))
    r = d["esearchresult"]
    print(f"  命中 {r['count']} 篇，取前 {len(r['idlist'])} 篇")
    return r["idlist"], r["count"]


def efetch_pubmed(pmids, email, api_key):
    data = _get("efetch.fcgi", {"id": ",".join(pmids),
                                "rettype": "abstract", "retmode": "xml"}, email, api_key)
    root = _parse_xml(data)
    out = {}
    for art in root.iter():
        if _local(art.tag) != "PubmedArticle":
            continue
        pmid = _find_local(art, "PMID")
        pmid = pmid.text if pmid is not None else ""
        if not pmid:
            continue
        article = _find_local(art, "Article")
        info = {"PMID": pmid}
        info["标题"] = (_find_local(article, "ArticleTitle").text or ""
                        if _find_local(article, "ArticleTitle") is not None else "")
        authors = []
        if article is not None:
            for a in article.iter():
                if _local(a.tag) == "Author":
                    ln = _find_local(a, "LastName")
                    fn = _find_local(a, "ForeName")
                    if fn is None:
                        fn = _find_local(a, "Initials")
                    ln = ln.text if ln is not None else ""
                    fn = fn.text if fn is not None else ""
                    authors.append((ln + " " + fn).strip())
        info["作者"] = "; ".join([x for x in authors if x])
        jt = _find_local(article, "Title")
        info["期刊"] = jt.text if jt is not None else ""
        yr = _find_local(article, "Year")
        info["年份"] = yr.text if yr is not None else ""
        vol = _find_local(article, "Volume")
        info["卷"] = vol.text if vol is not None else ""
        iss = _find_local(article, "Issue")
        info["期"] = iss.text if iss is not None else ""
        pg = _find_local(article, "MedlinePgn")
        info["页码"] = pg.text if pg is not None else ""
        seg = []
        abs_el = _find_local(article, "Abstract") if article is not None else None
        if abs_el is not None:
            for t in abs_el.iter():
                if _local(t.tag) == "AbstractText":
                    lab = t.get("Label")
                    txt = "".join(t.itertext()).strip()
                    seg.append(f"{lab}: {txt}" if lab else txt)
        info["摘要"] = " ".join(seg)
        info["链接"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        out[pmid] = info
    return out


def esummary_ids(pmids, email, api_key):
    data = _get("esummary.fcgi", {"id": ",".join(pmids), "retmode": "json"}, email, api_key)
    s = json.loads(data.decode("utf-8"))
    res = s.get("result", {})
    out = {}
    for pid in pmids:
        it = res.get(pid, {})
        doi = pmcid = ""
        for a in it.get("articleids", []):
            if a.get("idtype") == "doi":
                doi = a.get("value", "")
            elif a.get("idtype") == "pmc":
                pmcid = a.get("value", "")
        out[pid] = (doi, pmcid)
    return out


def _render(elem):
    tag = _local(elem.tag)
    txt = "".join(elem.itertext()).strip()
    if tag in ("sec", "body", "abstract"):
        inner = "".join(_render(c) for c in elem)
        return inner or (f"<p>{html.escape(txt)}</p>" if txt else "")
    if tag == "title":
        return f"<h3>{html.escape(txt)}</h3>"
    if tag == "p":
        return f"<p>{html.escape(txt)}</p>"
    if tag == "label":
        return f"<b>{html.escape(txt)}</b>"
    if tag in ("italic", "i", "em"):
        return f"<i>{html.escape(txt)}</i>"
    if tag in ("bold", "b"):
        return f"<b>{html.escape(txt)}</b>"
    inner = "".join(_render(c) for c in elem)
    return inner if inner else (f"<p>{html.escape(txt)}</p>" if txt else "")


def jats_to_html(data):
    root = _parse_xml(data)
    t = _find_local(root, "article-title")
    title = "".join(t.itertext()).strip() if t is not None else "全文"
    body = _find_local(root, "body")
    content = _render(body) if body is not None else ""
    if not content:
        abs_el = _find_local(root, "abstract")
        if abs_el is not None:
            content = "<h3>摘要</h3>" + _render(abs_el)
    parts = [
        "<html><head><meta charset='utf-8'><title>%s</title>" % html.escape(title),
        "<style>body{font-family:'Segoe UI',Georgia,serif;max-width:46em;margin:2em auto;"
        "line-height:1.7;padding:0 1em}h1{font-size:1.4em}h3{margin:1.4em 0 .4em;color:#1a3a5c}"
        "p{margin:.5em 0;text-align:justify}</style></head><body>",
        "<h1>%s</h1>" % html.escape(title),
    ]
    if content:
        parts.append(content)
    parts.append("</body></html>")
    return "\n".join(parts)


def fetch_pmc_fulltext(pmcid, email, api_key):
    num = pmcid.replace("PMC", "").strip()
    try:
        data = _get("efetch.fcgi", {"db": "pmc", "id": num, "retmode": "xml"}, email, api_key)
        return jats_to_html(data)
    except Exception:
        return None


# ---------------- 引用 / 导出 / 报告 ----------------
def _split_author(name):
    parts = name.strip().split()
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


def authors_gb(authors_str):
    names = [a for a in authors_str.split("; ") if a]
    if not names:
        return ""
    out = []
    for n in names[:3]:
        ln, fn = _split_author(n)
        out.append((ln.upper() + " " + fn) if fn else ln.upper())
    return ", ".join(out) + (", et al" if len(names) > 3 else "")


def authors_apa(authors_str):
    names = [a for a in authors_str.split("; ") if a]
    if not names:
        return ""
    out = []
    for n in names[:3]:
        ln, fn = _split_author(n)
        ini = " ".join([c[0] + "." for c in fn.split() if c]) if fn else ""
        out.append(f"{ln}, {ini}".strip())
    if len(names) > 3:
        return ", ".join(out) + ", et al."
    if len(out) == 2:
        return out[0] + ", & " + out[1]
    return ", ".join(out)


def reference_gb(info):
    au = authors_gb(info.get("作者", ""))
    title = info.get("标题", "").rstrip(".")
    journal = info.get("期刊", "")
    year = info.get("年份", "")
    vol = info.get("卷", "")
    issue = info.get("期", "")
    pages = info.get("页码", "")
    vol_issue = vol + (f"({issue})" if issue else "")
    tail = ": ".join([x for x in (vol_issue, pages) if x])
    return f"{au}. {title}[J]. {journal}, {year}, {tail}."


def reference_apa(info):
    au = authors_apa(info.get("作者", ""))
    title = info.get("标题", "").rstrip(".")
    journal = info.get("期刊", "")
    year = info.get("年份", "")
    vol = info.get("卷", "")
    issue = info.get("期", "")
    pages = info.get("页码", "")
    doi = info.get("DOI", "")
    vol_issue = vol + (f"({issue})" if issue else "")
    body = f"{journal}, {vol_issue}, {pages}" if vol_issue else journal
    ref = f"{au} ({year}). {title}. {body}."
    if doi:
        ref += f" https://doi.org/{doi}"
    return ref


def _authors_bib(authors_str):
    out = []
    for n in [a for a in authors_str.split("; ") if a]:
        ln, fn = _split_author(n)
        out.append(f"{ln}, {fn}".strip() if fn else ln)
    return " and ".join(out)


def make_references(rows):
    gb = [f"[{i + 1}] " + reference_gb(r) for i, r in enumerate(rows)]
    apa = [reference_apa(r) for i, r in enumerate(rows)]
    return "GB/T 7714 格式：\n" + "\n".join(gb) + "\n\nAPA 格式：\n" + "\n".join(apa)


def make_bibtex(rows):
    entries = []
    for r in rows:
        pmid = r.get("PMID", "")
        first = (r.get("作者", "").split(";")[0] if r.get("作者") else "").split()
        ln = first[0].lower() if first else "ref"
        key = f"{ln}{r.get('年份', '')}{pmid}"
        e = ["@article{" + key + ",",
             "  author = {" + _authors_bib(r.get("作者", "")) + "},",
             "  title = {" + r.get("标题", "").replace("{", "").replace("}", "") + "},",
             "  journal = {" + r.get("期刊", "") + "},",
             "  year = {" + r.get("年份", "") + "},"]
        if r.get("卷"):
            e.append(f"  volume = {{{r['卷']}}},")
        if r.get("期"):
            e.append(f"  number = {{{r['期']}}},")
        if r.get("页码"):
            e.append(f"  pages = {{{r['页码'].replace('-', '--')}}},")
        if r.get("DOI"):
            e.append(f"  doi = {{{r['DOI']}}},")
        e.append(f"  pmid = {{{pmid}}},")
        e.append(f"  url = {{https://pubmed.ncbi.nlm.nih.gov/{pmid}/}}")
        e.append("}")
        entries.append("\n".join(e))
    return "\n\n".join(entries)


def make_ris(rows):
    recs = []
    for r in rows:
        lines = ["TY  - JOUR"]
        for n in [a for a in r.get("作者", "").split("; ") if a]:
            lines.append("AU  - " + n)
        lines.append("TI  - " + r.get("标题", ""))
        lines.append("JO  - " + r.get("期刊", ""))
        lines.append("PY  - " + r.get("年份", ""))
        if r.get("卷"):
            lines.append("VL  - " + r["卷"])
        if r.get("期"):
            lines.append("IS  - " + r["期"])
        if r.get("页码"):
            parts = r["页码"].split("-")
            lines.append("SP  - " + parts[0])
            if len(parts) > 1 and parts[1]:
                lines.append("EP  - " + parts[1])
        if r.get("DOI"):
            lines.append("DO  - " + r["DOI"])
        lines.append("AN  - " + r.get("PMID", ""))
        lines.append("UR  - " + f"https://pubmed.ncbi.nlm.nih.gov/{r.get('PMID', '')}/")
        lines.append("ER  - ")
        recs.append("\n".join(lines))
    return "\n\n".join(recs)


def make_html(rows):
    cards = []
    for r in rows:
        title = r.get("标题", "")
        authors = r.get("作者", "")
        journal = r.get("期刊", "")
        year = r.get("年份", "")
        doi = r.get("DOI", "")
        link = r.get("链接", "")
        abstract = r.get("摘要", "")
        full = r.get("全文文件", "")
        full_link = f'<a href="全文/{html.escape(full)}">📄 全文</a>' if full else ""
        doi_link = f'<a href="https://doi.org/{html.escape(doi)}">DOI</a>' if doi else ""
        cards.append(f"""<div class="card">
<div class="title"><a href="{html.escape(link)}">{html.escape(title)}</a></div>
<div class="meta">{html.escape(authors)} · {html.escape(journal)} · {html.escape(year)}</div>
<div class="abs">{html.escape(abstract[:400])}{"…" if len(abstract) > 400 else ""}</div>
<div class="links">{full_link}<a href="{html.escape(link)}">PubMed</a>{doi_link}</div>
</div>""")
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>检索结果</title>"
            "<style>body{font-family:'Segoe UI',sans-serif;max-width:900px;margin:2em auto;"
            "padding:0 1em;background:#f7f8fa}.card{background:#fff;border:1px solid #e3e6ea;"
            "border-radius:8px;padding:16px 18px;margin:14px 0}.title{font-size:1.05em;"
            "font-weight:600;margin-bottom:6px}.title a{color:#1a3a5c;text-decoration:none}"
            ".meta{color:#666;font-size:.85em;margin-bottom:8px}.abs{color:#333;font-size:.9em;"
            "line-height:1.5}.links{margin-top:10px;font-size:.85em}.links a{color:#0b6ec9;"
            "margin-right:14px;text-decoration:none}</style></head><body>"
            f"<h1>检索结果（共 {len(rows)} 篇）</h1>" + "".join(cards) + "</body></html>")


def append_log(topic, query, count, n_rows, oa_count, outdir):
    try:
        with open(os.path.join(cc.base_dir(), "log.txt"), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n")
            f.write(f"主题：{topic}\n")
            f.write(f"检索式：{query}\n")
            f.write(f"命中 {count} 篇，取 {n_rows} 篇，OA 全文 {oa_count} 篇\n")
            f.write(f"结果目录：{outdir}\n")
            f.write("-" * 40 + "\n")
    except Exception:
        pass


def esummary_brief(pmids, email, api_key):
    """用 esummary 批量拿标题/年份/期刊（用于命中汇总），分批 200"""
    out = {}
    for i in range(0, len(pmids), 200):
        chunk = pmids[i:i + 200]
        data = _get("esummary.fcgi", {"id": ",".join(chunk), "retmode": "json"}, email, api_key)
        s = json.loads(data.decode("utf-8"))
        res = s.get("result", {})
        for pid in chunk:
            it = res.get(pid, {})
            if it:
                pubdate = it.get("pubdate", "")
                out[pid] = {
                    "标题": it.get("title", ""),
                    "年份": pubdate[:4],
                    "期刊": it.get("fulljournalname", "") or it.get("source", ""),
                }
        time.sleep(0.4 if not api_key else 0.15)
    return out


def make_summary(pmids, brief, topic, query, outdir):
    """生成命中标题汇总（带生成时间）"""
    lines = [
        "PubMed 命中文献汇总",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"检索主题：{topic}",
        f"检索式：{query}",
        f"共 {len(pmids)} 篇（按相关度排序，仅列标题）",
        "=" * 60,
        "",
        "说明：想额外下载某篇，把它的 PMID 填进程序目录的「待下载.txt」（一行一个），下次运行会一并下载。",
        "",
    ]
    for i, pid in enumerate(pmids):
        b = brief.get(pid, {})
        lines.append(f"{i + 1:>4}. PMID:{pid}  {b.get('标题', '')}  ({b.get('年份', '')})  {b.get('期刊', '')}")
    path = os.path.join(outdir, "命中汇总.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def load_downloaded():
    """读已下载清单 downloaded.txt，返回 PMID 集合"""
    path = os.path.join(cc.base_dir(), "downloaded.txt")
    s = set()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        s.add(line.split("\t")[0].strip())
        except Exception:
            pass
    return s


def save_downloaded(records):
    """追加已下载记录：PMID + 时间 + 标题"""
    path = os.path.join(cc.base_dir(), "downloaded.txt")
    with open(path, "a", encoding="utf-8") as f:
        for pmid, title in records:
            f.write(f"{pmid}\t{time.strftime('%Y-%m-%d %H:%M:%S')}\t{title}\n")


def load_todownload():
    """读待下载清单 待下载.txt，返回 PMID 列表"""
    path = os.path.join(cc.base_dir(), "待下载.txt")
    ids = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        ids.append(line.split()[0].strip())
        except Exception:
            pass
    return ids


def download_batch(pmid_list, meta, idmap, email, api_key, cfg, full_dir, start_idx):
    """下载一批文献的全文，返回 (rows, oa_count, downloaded_records)"""
    rows, oa_count, rec = [], 0, []
    for i, pid in enumerate(pmid_list):
        info = meta.get(pid, {"PMID": pid})
        doi, pmcid = idmap.get(pid, ("", ""))
        info["DOI"] = doi
        info["PMCID"] = pmcid
        full_html = None
        if pmcid and cfg["download_fulltext"]:
            print(f"  [{start_idx + i + 1}/{len(pmid_list)}] 下载全文 {pmcid} ...")
            full_html = fetch_pmc_fulltext(pmcid, email, api_key)
            time.sleep(0.4 if not api_key else 0.15)
        fname = ""
        if full_html:
            oa_count += 1
            short = re.sub(r'[\\/:*?"<>|]', "", info.get("标题", ""))[:50] or pid
            fname = f"{start_idx + i + 1:03d}_{short}.html"
            with open(os.path.join(full_dir, fname), "w", encoding="utf-8") as f:
                f.write(full_html)
            info["全文文件"] = fname
            info["是否OA"] = "是"
            rec.append((pid, info.get("标题", "")))
        else:
            info["全文文件"] = ""
            info["是否OA"] = "否"
        rows.append(info)
    return rows, oa_count, rec


# ---------------- 主流程 ----------------
def main():
    cc.print_banner("PubMed AI 文献检索")
    cfg = cc.load_config()
    if cfg is None:
        print("  未找到有效配置。")
        print("  请先运行「配置设置.exe」完成配置，再启动本程序。")
        input("\n  按回车键关闭...")
        return
    if not cfg.get("email") or "your_email" in cfg["email"] or "@example.com" in cfg["email"]:
        print("  配置里还没填邮箱，请用「配置设置.exe」填写。")
        input("\n  按回车键关闭...")
        return
    if not cfg.get("deepseek_api_key") or "这里填" in cfg["deepseek_api_key"]:
        print("  配置里还没填 DeepSeek Key，请用「配置设置.exe」填写。")
        input("\n  按回车键关闭...")
        return

    topic = input("\n请输入研究主题（中文或英文）：").strip()
    if not topic:
        print("未输入主题，退出。")
        input("\n  按回车键关闭...")
        return

    print("\n  正在让 AI 生成检索式...")
    try:
        query, explain = gen_query(topic, cfg)
    except Exception as e:
        print(f"  AI 调用失败：{e}")
        print("  请用「配置设置.exe」检查 API 地址 / Key。")
        input("\n  按回车键关闭...")
        return

    if explain:
        print(f"\n  【解释】{explain}")
    print(f"\n  生成的 PubMed 检索式：\n  {query}")

    if cfg["confirm_query"]:
        ans = input("\n  回车确认开始检索；或直接输入修改后的检索式：").strip()
        if ans:
            query = ans

    email, api_key = cfg["email"], cfg["ncbi_api_key"]
    sort_param = "pub_date" if cfg.get("sort") == "date" else "relevance"
    print()
    fetch_n = max(cfg["summary_limit"], cfg["max_results"])
    if fetch_n > 10000:
        fetch_n = 10000
    pmids, count = esearch(query, fetch_n, email, api_key, sort_param)
    if not pmids:
        print("  无结果，换主题或改检索式。")
        input("\n  按回车键关闭...")
        return

    out_base = cfg["output_dir"] if cfg["output_dir"] else cc.base_dir()
    outdir = os.path.join(out_base, "检索结果_" + time.strftime("%Y%m%d_%H%M%S"))
    full_dir = os.path.join(outdir, "全文")
    os.makedirs(full_dir, exist_ok=True)

    # 1) 生成命中标题汇总
    summary_pmids = pmids[:cfg["summary_limit"]]
    print(f"  正在生成命中汇总（前 {len(summary_pmids)} 篇标题）...")
    brief = esummary_brief(summary_pmids, email, api_key)
    make_summary(summary_pmids, brief, topic, query, outdir)

    # 2) 确定下载集合：前 max_results 篇 + 待下载.txt
    todo_pmids = pmids[:cfg["max_results"]]
    extra = load_todownload()
    if extra:
        for pid in extra:
            if pid not in todo_pmids:
                todo_pmids.append(pid)
        print(f"  已并入待下载清单 {len(extra)} 个 PMID。")

    print("  正在抓取摘要与元数据...")
    meta = efetch_pubmed(todo_pmids, email, api_key)
    time.sleep(0.4)
    idmap = esummary_ids(todo_pmids, email, api_key)

    # 3) 去重：分新/旧
    downloaded = load_downloaded()
    new_pmids = [p for p in todo_pmids if p not in downloaded]
    old_pmids = [p for p in todo_pmids if p in downloaded]
    if old_pmids:
        print(f"  其中 {len(old_pmids)} 篇之前下载过（稍后询问是否重下）。")

    # 4) 先下载新文献
    rows, oa_count, rec = download_batch(new_pmids, meta, idmap, email, api_key, cfg, full_dir, 0)

    # 5) 询问是否重新下载旧的
    if old_pmids:
        ans = input(f"\n  有 {len(old_pmids)} 篇之前下载过，是否重新下载？(y/n)：").strip().lower()
        if ans in ("y", "yes", "1"):
            r2, oa2, rec2 = download_batch(old_pmids, meta, idmap, email, api_key, cfg, full_dir, len(rows))
            rows.extend(r2)
            oa_count += oa2
            rec.extend(rec2)
        else:
            print("  已跳过这些之前下载过的文献。")

    # 6) 记录本次新下载成功的
    if rec:
        save_downloaded(rec)

    fields = ["PMID", "标题", "作者", "期刊", "年份", "卷", "期", "页码", "DOI", "链接", "是否OA", "全文文件", "摘要"]
    csv_path = os.path.join(outdir, "文献清单.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # 引用 / 导出 / 报告
    with open(os.path.join(outdir, "参考文献.txt"), "w", encoding="utf-8") as f:
        f.write(make_references(rows))
    with open(os.path.join(outdir, "文献.bib"), "w", encoding="utf-8") as f:
        f.write(make_bibtex(rows))
    with open(os.path.join(outdir, "文献.ris"), "w", encoding="utf-8") as f:
        f.write(make_ris(rows))
    with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
        f.write(make_html(rows))

    append_log(topic, query, count, len(rows), oa_count, outdir)

    print(f"\n[完成] 共 {len(rows)} 篇，其中 OA 全文 {oa_count} 篇")
    print(f"  结果目录：{outdir}")
    print("  已生成：命中汇总.txt / 文献清单.csv / 参考文献.txt / 文献.bib / 文献.ris / index.html")

    try:
        os.startfile(outdir)
    except Exception:
        pass

    input("\n  按回车键关闭窗口...")


if __name__ == "__main__":
    main()
