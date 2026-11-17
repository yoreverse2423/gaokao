#!/usr/bin/env python3
"""打包回归：白名单、新学科学生页、私档排除、本地链接、单文件说明。"""
from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import package_site as pkg  # noqa: E402


def test_whitelist_and_new_subject():
    tmp = Path(tempfile.mkdtemp(prefix="gaokao-pack-"))
    try:
        data = tmp / "data"
        data.mkdir()
        (data / "历史.json").write_text(
            '{"resources":[{"url":"materials/history/自定义学生单.html"}]}',
            encoding="utf-8",
        )
        (tmp / "materials/history").mkdir(parents=True)
        (tmp / "materials/biology").mkdir(parents=True)
        (tmp / "materials/history/第二周-学生页.md").write_text("# 学生\n\n只看题面。\n", encoding="utf-8")
        (tmp / "materials/history/自定义学生单.html").write_text("<p>学生单</p>", encoding="utf-8")
        (tmp / "materials/history/PRIVATE-key.md").write_text("secret", encoding="utf-8")
        (tmp / "materials/biology/bot-only-批改.md").write_text("no", encoding="utf-8")
        (tmp / "materials/biology/随机笔记.md").write_text("内部", encoding="utf-8")
        (tmp / "work").mkdir()
        (tmp / "work/note.md").write_text("no", encoding="utf-8")
        (tmp / "reviews").mkdir()
        (tmp / "reviews/x.md").write_text("no", encoding="utf-8")
        files = pkg.collect_source_files(tmp)
        assert "materials/history/第二周-学生页.md" in files
        assert "materials/history/自定义学生单.html" in files
        assert "materials/biology/随机笔记.md" not in files
        assert all("PRIVATE" not in n and "bot-only" not in n and not n.startswith("work/") and not n.startswith("reviews/") for n in files)
        page = pkg.render_md("# 标题\n\n<script>alert(1)</script>\n\n- 一项\n")
        assert "<h1>" in page and "&lt;script&gt;" in page and "<li>" in page
        assert pkg.rel_to("materials/geo/recall.html", "index.html") == "../../index.html"
        fixed = pkg.rewrite_back_links('<a href="../../index.html">返回</a>', "materials/geo/recall.html")
        assert 'href="../../index.html"' in fixed
        shallow = pkg.rewrite_back_links('<a href="../../index.html">返回</a>', "materials/readme.html")
        assert 'href="../index.html"' in shallow
    finally:
        shutil.rmtree(tmp)


def test_real_package_roundtrip():
    probe = ROOT / "materials" / "_pkgtest"
    probe.mkdir(parents=True, exist_ok=True)
    student = probe / "新学科-学生页.md"
    private = probe / "PRIVATE-note.md"
    noise = probe / "随机笔记.md"
    student.write_text("# 打包探针\n\n这不是题目，只给打包测试。\n", encoding="utf-8")
    private.write_text("do not pack", encoding="utf-8")
    noise.write_text("do not pack", encoding="utf-8")
    try:
        zip_path = pkg.package(ROOT)
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
        assert "index.html" in names and pkg.SINGLE_NAME in names
        assert names  # populated
        single = zipfile.ZipFile(zip_path).read("index.html")
        other = zipfile.ZipFile(zip_path).read(pkg.SINGLE_NAME)
        assert single == other
        text = single.decode("utf-8")
        assert "不是完整离线讲义" in text
        assert "完全独立" not in text
        assert "不会同步到手表或学习 App" in text
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert "materials/english/周末阅读-学生页.html" in names
            assert "materials/english/周末阅读-学生页.md" in names
            assert "materials/geo/recall.html" in names
            assert "materials/_pkgtest/新学科-学生页.md" in names
            assert "materials/_pkgtest/新学科-学生页.html" in names
            assert "materials/_pkgtest/随机笔记.md" not in names
            assert not any("PRIVATE" in n or "bot-only" in n or n.startswith(("work/", "reviews/", "backups/")) for n in names)
            recall = zf.read("materials/geo/recall.html").decode("utf-8")
            assert 'href="../../index.html"' in recall
            bundle = zf.read("data/bundle.js").decode("utf-8")
            assert "materials/english/周末阅读-学生页.html" in bundle
            assert "materials/english/周末阅读-学生页.md" not in bundle
            # 磁盘上的课表源文件仍指向 md，不能被打包过程改写成 html。
            disk = (ROOT / "data" / "英语.json").read_text(encoding="utf-8")
            assert "materials/english/周末阅读-学生页.md" in disk
            errors = pkg.check_links({n: zf.read(n) for n in names})
            assert errors == [], errors
            eng = zf.read("materials/english/周末阅读-学生页.html").decode("utf-8")
            assert "The Lost Lunch Box" in eng
            assert "没有标准答案" in eng
            assert "正确答案" not in eng
            assert "pack-fit" in eng
    finally:
        shutil.rmtree(probe, ignore_errors=True)
        pkg.package(ROOT)


if __name__ == "__main__":
    test_whitelist_and_new_subject()
    test_real_package_roundtrip()
    print("PASS: package whitelist, new subject, private exclusion, links, single-file note")
