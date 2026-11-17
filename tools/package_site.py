#!/usr/bin/env python3
"""白名单打包：完整离线包 + 明确命名的主界面单文件。

不修改 data/ 与 materials/ 源文件。材料 HTML、返回链接和课表里的
学生页链接只写进 dist。单文件不含讲义，不能当成完整独立站点。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ZIP_NAME = "备考计划网站.zip"
SINGLE_NAME = "主界面-单文件.html"

DENY_DIRS = {
    "work", "reviews", "backups", "backup", "private",
    ".git", "dist", "__pycache__", "node_modules",
}
DENY_NAME_RE = re.compile(
    r"(PRIVATE|bot-only|bot_only|提示词|\.env\b|credentials|id_rsa|secret|密码)",
    re.I,
)
ANSWER_OK = ("无答案", "不含答案", "不附答案", "没有答案")
STUDENT_MARKERS = ("学生", "打开说明", "离线", "课标", "来源与边界", "knowledge.html", "recall.html")
STUDENT_EXT = {".md", ".html", ".htm", ".txt", ".pdf"}
ROOT_DOCS = ("SCHEMA.md", "总课表.md", "打开说明.txt", "首周任务_学生版.md", "验证报告.md")
FIT_CSS = (
    "<style id=\"pack-fit\">"
    "html{max-width:100%}"
    "body{overflow-wrap:anywhere;word-break:break-word;max-width:42rem;"
    "margin:0 auto;padding:12px 14px;font:17px/1.7 system-ui,"
    "\"PingFang SC\",\"Microsoft YaHei\",sans-serif}"
    "pre,code,a,p,li,h1,h2,h3{overflow-wrap:anywhere}"
    "img,svg,table,pre{max-width:100%}"
    "a{word-break:break-word}"
    "@media print{body{background:#fff;color:#000;font:12pt/1.6 serif}"
    "a{color:#000;text-decoration:none}}"
    "</style>"
)
SINGLE_NOTE = (
    "不会同步到手表或学习 App。本文件是主界面单文件：样式、脚本和课表数据已写在文件内；"
    "各科讲义在同级 materials/ 目录，没有装进本文件，所以它不是完整离线讲义。"
)
LINK_RE = re.compile(r"""(?:href|src)\s*=\s*(["'])([^"']+)\1""", re.I)
MD_LINK_RE = re.compile(r"""\[[^\]]*\]\(([^)\s]+)\)""")


def denied_name(name: str) -> bool:
    if DENY_NAME_RE.search(name):
        return True
    if "答案" in name and not any(ok in name for ok in ANSWER_OK):
        return True
    return False


def denied_rel(rel: str) -> bool:
    parts = Path(rel).parts
    if any(p.lower() in DENY_DIRS or p.startswith(".") for p in parts):
        return True
    return any(denied_name(p) for p in parts)


def referenced_materials(root: Path = ROOT) -> set[str]:
    found = set()
    data = root / "data"
    if not data.is_dir():
        return found
    for path in data.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"""materials/[^"'\s]+""", text):
            found.add(m.group(0))
    return found


def is_student_material(rel: str, referenced: set[str]) -> bool:
    path = Path(rel)
    if not path.parts or path.parts[0] != "materials" or len(path.parts) < 2:
        return False
    if denied_rel(rel):
        return False
    if path.suffix.lower() not in STUDENT_EXT:
        return False
    if rel in referenced:
        return True
    return any(mark in path.name for mark in STUDENT_MARKERS)


def collect_source_files(root: Path = ROOT) -> dict[str, bytes]:
    """返回将进入压缩包的源文件。不含生成的单文件和由 Markdown 转出的 HTML。"""
    referenced = referenced_materials(root)
    files: dict[str, bytes] = {}
    refused = []

    def add(rel: str, data: bytes):
        rel = rel.replace("\\", "/")
        if denied_rel(rel):
            refused.append(rel)
            return
        files[rel] = data

    for name in ("app.js", "style.css", "index.html"):
        path = root / name
        if path.is_file():
            arc = "index.source.html" if name == "index.html" else name
            add(arc, path.read_bytes())
    data = root / "data"
    if data.is_dir():
        for path in sorted(data.glob("*")):
            if path.is_file() and path.suffix.lower() in {".json", ".js"}:
                add(f"data/{path.name}", path.read_bytes())
    tools = root / "tools"
    if tools.is_dir():
        for path in sorted(tools.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".cjs", ".js", ".md", ".sh"}:
                continue
            add(str(path.relative_to(root)).replace("\\", "/"), path.read_bytes())
    for name in ROOT_DOCS:
        path = root / name
        if path.is_file():
            add(name, path.read_bytes())
    for path in sorted(root.glob("验收记录*.md")) + sorted(root.glob("复核报告*.md")):
        add(path.name, path.read_bytes())
    materials = root / "materials"
    if materials.is_dir():
        for path in sorted(materials.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root)).replace("\\", "/")
            if is_student_material(rel, referenced):
                add(rel, path.read_bytes())
            elif rel in referenced and denied_rel(rel):
                refused.append(rel)
    if refused:
        raise SystemExit("拒绝打包私档或被点名的非学生文件:\n" + "\n".join(sorted(set(refused))))
    missing = [rel for rel in sorted(referenced) if rel not in files and not denied_rel(rel)]
    # referenced md/html must be packed; other missing refs are reported by the link check later
    missing = [rel for rel in missing if Path(rel).suffix.lower() in STUDENT_EXT]
    if missing:
        raise SystemExit("课表指向的学生材料不在白名单结果中:\n" + "\n".join(missing))
    return files


def render_md(text: str) -> str:
    """把学生 Markdown 转成 HTML 片段。先转义，不执行原文里的标签，也不补答案。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    html = []
    para = []
    list_tag = None

    def inline(s: str) -> str:
        s = (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        def link(m):
            label, url = m.group(1), m.group(2).strip()
            if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I) and not re.match(r"https?:", url, re.I):
                url = "#"
            url = url.replace('"', "%22")
            return f'<a href="{url}">{label}</a>'
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)

    def flush_para():
        if para:
            html.append("<p>" + "<br>\n".join(inline(x) for x in para) + "</p>")
            para.clear()

    def close_list():
        nonlocal list_tag
        if list_tag:
            html.append(f"</{list_tag}>")
            list_tag = None

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            close_list()
            continue
        if line.startswith("#"):
            flush_para()
            close_list()
            level = min(len(line) - len(line.lstrip("#")), 3)
            html.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            flush_para()
            tag = "ol" if m.group(2)[:1].isdigit() else "ul"
            if list_tag != tag:
                close_list()
                html.append(f"<{tag}>")
                list_tag = tag
            html.append(f"<li>{inline(m.group(3))}</li>")
            continue
        if line.startswith(">"):
            flush_para()
            close_list()
            html.append(f"<blockquote><p>{inline(line[1:].strip())}</p></blockquote>")
            continue
        close_list()
        para.append(line.strip())
    flush_para()
    close_list()
    return "\n".join(html)


def rel_to(from_arc: str, to_arc: str) -> str:
    base = Path(from_arc).parent.as_posix()
    rel = os.path.relpath(to_arc, base if base != "." else ".")
    return rel.replace("\\", "/")


def wrap_student_html(title: str, body: str, back: str) -> str:
    return (
        "<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{title}</title>{FIT_CSS}</head><body>"
        f"<p><a href=\"{back}\">返回计划网站</a></p>"
        f"<article>{body}</article>"
        "<p>本页由学生材料原文生成，供浏览器阅读和打印，不附答案。</p>"
        "</body></html>"
    )


def inject_fit(html: str) -> str:
    if "pack-fit" in html:
        return html
    if "<head>" in html:
        return html.replace("<head>", "<head>" + FIT_CSS, 1)
    return FIT_CSS + html


def rewrite_back_links(html: str, arcname: str) -> str:
    target = rel_to(arcname, "index.html")

    def repl(m):
        quote, url = m.group(1), m.group(2)
        path = url.split("#", 1)[0].split("?", 1)[0]
        base = path.rsplit("/", 1)[-1]
        if base in {"index.html", "备考计划.html", SINGLE_NAME}:
            suffix = url[len(path):]
            return f"href={quote}{target}{suffix}{quote}"
        return m.group(0)

    return re.sub(r"""href\s*=\s*(["'])([^"']+)\1""", repl, html, flags=re.I)


def add_rendered_pages(files: dict[str, bytes]) -> None:
    md_names = [name for name in list(files) if name.endswith(".md")]
    for name in md_names:
        html_name = name[:-3] + ".html"
        if html_name in files:
            continue
        title = Path(name).stem
        body = render_md(files[name].decode("utf-8"))
        page = wrap_student_html(title, body, rel_to(html_name, "index.html"))
        files[html_name] = page.encode("utf-8")
    for name in list(files):
        if not name.endswith(".html") or name in {"index.html", SINGLE_NAME, "index.source.html"}:
            continue
        text = files[name].decode("utf-8")
        text = inject_fit(text)
        text = rewrite_back_links(text, name)
        files[name] = text.encode("utf-8")
    bundle = files.get("data/bundle.js")
    if bundle is None:
        return
    text = bundle.decode("utf-8")
    for name in md_names:
        html_name = name[:-3] + ".html"
        if html_name in files:
            text = text.replace(name, html_name)
    files["data/bundle.js"] = text.encode("utf-8")


def build_single(root: Path, files: dict[str, bytes]) -> str:
    html = (root / "index.html").read_text(encoding="utf-8")
    html = html.replace("不会同步到手表或学习 App。", SINGLE_NOTE)
    css = files["style.css"].decode("utf-8")
    html = html.replace('<link rel="stylesheet" href="style.css">', "<style>" + css + "</style>")
    for name in ("data/bundle.js", "app.js"):
        script = files[name].decode("utf-8").replace("</script", "<\\/script")
        html = html.replace(f'<script src="{name}"></script>', "<script>" + script + "</script>")
    if "不是完整离线讲义" not in html:
        raise SystemExit("单文件缺少“不是完整离线讲义”说明")
    if "完全独立" in html:
        raise SystemExit("单文件不应宣称完全独立")
    return html


def local_targets(arc: str, url: str):
    url = url.strip()
    if not url or url.startswith(("#", "mailto:", "data:")):
        return None
    if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
        if url.startswith("http://") or url.startswith("https://"):
            return None
        return "BAD:" + url
    path = url.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return None
    if path.startswith("/"):
        joined = path.lstrip("/")
    else:
        base = Path(arc).parent.as_posix()
        joined = os.path.normpath(os.path.join("." if base == "." else base, path))
    joined = joined.replace("\\", "/")
    if joined.startswith("../") or joined == "..":
        return "OUT:" + joined
    return joined


def check_links(files: dict[str, bytes]) -> list[str]:
    errors = []
    for arc, data in sorted(files.items()):
        if not arc.endswith((".html", ".htm", ".md")):
            continue
        text = data.decode("utf-8", "replace")
        urls = [m.group(2) for m in LINK_RE.finditer(text)]
        if arc.endswith(".md"):
            urls += MD_LINK_RE.findall(text)
        for url in urls:
            if "${" in url or url.startswith("<%"):
                continue
            target = local_targets(arc, url)
            if target is None:
                continue
            if target.startswith("BAD:") or target.startswith("OUT:"):
                errors.append(f"{arc} -> {url} ({target})")
                continue
            if target not in files:
                errors.append(f"{arc} -> {url} 缺少 {target}")
    bundle = files.get("data/bundle.js", b"").decode("utf-8", "replace")
    for rel in sorted(set(re.findall(r"materials/[A-Za-z0-9_./\-\u4e00-\u9fff]+", bundle))):
        if rel.endswith("/") or "." not in Path(rel).name:
            continue
        if rel not in files:
            errors.append(f"data/bundle.js -> {rel} 不在包内")
    return errors


def write_outputs(files: dict[str, bytes]) -> Path:
    if DIST.exists():
        for child in DIST.iterdir():
            if child.is_file():
                child.unlink()
            elif child.is_dir() and child.name == "site":
                for p in sorted(child.rglob("*"), reverse=True):
                    if p.is_file():
                        p.unlink()
                    elif p.is_dir():
                        p.rmdir()
                child.rmdir()
    site = DIST / "site"
    for rel, data in files.items():
        path = site / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    zip_path = DIST / ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(files):
            zf.write(site / rel, rel)
    return zip_path


def package(root: Path = ROOT) -> Path:
    subprocess.run([sys.executable, str(root / "tools/validate_plan.py")], check=True)
    subprocess.run([sys.executable, str(root / "tools/build.py")], check=True)
    files = collect_source_files(root)
    add_rendered_pages(files)
    single = build_single(root, files).encode("utf-8")
    files["index.html"] = single
    files[SINGLE_NAME] = single
    # 源课表 json 保持材料的 .md 路径；学生打开的 bundle 和单文件改指向生成的 html。
    errors = check_links(files)
    if errors:
        raise SystemExit("本地链接校验失败:\n" + "\n".join(errors))
    for rel in files:
        if denied_rel(rel):
            raise SystemExit(f"包内仍有被拒绝路径: {rel}")
    return write_outputs(files)


def main():
    zip_path = package(ROOT)
    print(f"Packaged {zip_path}")
    print(f"Single file is index.html and {SINGLE_NAME}; it still needs materials/ beside it.")


if __name__ == "__main__":
    main()
