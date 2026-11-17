#!/usr/bin/env python3
"""校验六科排程：撞车、每日必做数、周末块数、单块时长、晚自习类型、疑似答案。"""
from __future__ import annotations
import json, re, sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "地理"]
DAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
SCHOOL_SLOTS = {"午间", "傍晚", "夜间", "晚自习"}
HOLIDAY = {11, 12, 13, 14}
SPRING = 12
ANSWER_RE = re.compile(
    r"(正确答案|标准答案是|参考答案是|答案是[：:]|答案为|答案：|答案:|选项[ABCD]正确|故选[ABCD]|答案[ABCD](?![项面]))"
)
NEG_ANSWER_RE = re.compile(r"(不附答案|不含答案|不看答案|不对答案|没有答案|勿写答案|不要.*答案|不给答案|题面.*答案|对照评分|对答案标错因|对完后再)")
PRACTICE_RE = re.compile(r"(套卷|限时整卷|主观题作答|做\d+道选择|计算题|跟\w+bot学：)")
RECITE_RE = re.compile(r"(背记|背诵|默写|默填|空白图|离线背|词表|公式卡|框架|合上资料|闭卷|知识卡|回忆)")


def load_all():
    out = {}
    for s in SUBJECTS:
        out[s] = json.loads((DATA / f"{s}.json").read_text(encoding="utf-8"))
    cal = json.loads((DATA / "calendar.json").read_text(encoding="utf-8"))
    return out, cal


def is_must(task: str) -> bool:
    return "【小必做】" in (task or "")

def is_marked(task: str) -> bool:
    task = task or ""
    return "【小必做】" in task or "【小必做·" in task or "【可选】" in task or "【可选·" in task


def iter_tasks(subs):
    for s, d in subs.items():
        for w in d["weeks"]:
            for t in (w.get("weekday") or []) + (w.get("weekend") or []):
                yield s, w, t


def walk_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def main():
    subs, cal = load_all()
    errors, warns = [], []

    # --- collisions ---
    # key: (week, day, slot) -> list of (subject, min, type, task[:40])
    occ = defaultdict(list)
    for s, w, t in iter_tasks(subs):
        day = t.get("day")
        slot = t.get("slot") or ("周末" if t.get("day") in ("周六", "周日") else "?")
        if t.get("day") in ("周六", "周日"):
            slot = "周末"
        occ[(w["week"], day, slot)].append((s, t.get("min"), t.get("type"), t.get("task") or ""))

    collisions = 0
    for (wk, day, slot), lst in sorted(occ.items()):
        names = [x[0] for x in lst]
        if slot == "周末":
            continue
        if slot == "晚自习":
            # 允许多科背诵；检查类型与总时长
            bad_type = [x for x in lst if x[2] != "背诵"]
            if bad_type:
                errors.append(f"W{wk} {day} 晚自习非背诵: {[(x[0], x[2]) for x in bad_type]}")
            total = sum(x[1] or 0 for x in lst)
            if total > 120:
                errors.append(f"W{wk} {day} 晚自习总时长{total}>120分钟（作业后剩余）: {[(x[0], x[1]) for x in lst]}")
            if len(lst) > 2:
                warns.append(f"W{wk} {day} 晚自习{len(lst)}份，超过建议2份: {[x[0] for x in lst]}")
            continue
        if len(set(names)) > 1 or len(names) > 1:
            collisions += 1
            errors.append(f"撞车 W{wk} {day} {slot}: {[(x[0], x[1], x[2]) for x in lst]}")

    # --- duration ---
    for s, w, t in iter_tasks(subs):
        m = t.get("min")
        if m is None or not (20 <= m <= 30):
            errors.append(f"时长越界 {s} W{w['week']} {t.get('day')} {t.get('slot')}: min={m}")
        if "slot" not in t and t.get("day") not in ("周六", "周日"):
            errors.append(f"上学日缺 slot {s} W{w['week']} {t}")
        if t.get("day") in DAYS and t.get("day") not in ("周六", "周日"):
            if t.get("slot") not in SCHOOL_SLOTS:
                errors.append(f"非法 slot {s} W{w['week']} {t.get('slot')}")
        if t.get("slot") == "晚自习" and t.get("type") != "背诵":
            errors.append(f"晚自习类型 {s} W{w['week']} {t.get('day')} type={t.get('type')}")
        if t.get("slot") == "晚自习":
            task = t.get("task") or ""
            # 地理等：晚自习不得把练习伪装成背诵（既像练习又没有任何背诵动词）
            if PRACTICE_RE.search(task) and not RECITE_RE.search(task):
                errors.append(f"晚自习内容像练习 {s} W{w['week']} {t.get('day')}: {task[:80]}")
        if t.get("slot") == "夜间":
            task = t.get("task") or ""
            if is_must(task):
                errors.append(f"夜间被标小必做 {s} W{w['week']} {t.get('day')}")
            if "累了跳过" not in task:
                errors.append(f"夜间未标累了跳过 {s} W{w['week']} {t.get('day')}")
        # 必做/可选标记
        task = t.get("task") or ""
        if not is_marked(task):
            errors.append(f"未标必做/可选 {s} W{w['week']} {t.get('day')} {t.get('slot')}: {task[:50]}")

    # --- daily must-do and weekend caps ---
    for wk in range(1, 30):
        by_day = {d: [] for d in DAYS}
        for s, d in subs.items():
            w = next(x for x in d["weeks"] if x["week"] == wk)
            for t in (w.get("weekday") or []) + (w.get("weekend") or []):
                by_day[t["day"]].append((s, t))
        sat_n = len(by_day["周六"])
        sun_n = len(by_day["周日"])
        if sat_n > 4:
            errors.append(f"W{wk} 周六{sat_n}块>4: {[x[0] for x in by_day['周六']]}")
        if sun_n > 3:
            errors.append(f"W{wk} 周日{sun_n}块>3: {[x[0] for x in by_day['周日']]}")
        for day in DAYS:
            musts = [(s, t) for s, t in by_day[day] if is_must(t.get("task") or "")]
            if len(musts) > 1:
                errors.append(f"W{wk} {day} 小必做{len(musts)}个>1: {[s for s,_ in musts]}")
            # 上学周工作日应恰好 1 个必做；假期有任务的日子 ≤1，春节允许部分天为 0
            if wk not in HOLIDAY and day in ("周一", "周二", "周三", "周四", "周五"):
                if len(musts) != 1:
                    errors.append(f"W{wk} {day} 上学日小必做数={len(musts)}（应为1）: {[s for s,_ in musts]}")
            if wk not in HOLIDAY and day in ("周六", "周日") and by_day[day]:
                if len(musts) != 1:
                    errors.append(f"W{wk} {day} 周末有任务但小必做数={len(musts)}（应为1）")
            if wk in HOLIDAY and wk != SPRING and day in ("周一", "周二", "周三", "周四", "周五", "周六", "周日") and by_day[day]:
                if len(musts) != 1:
                    errors.append(f"W{wk} {day} 假期有任务但小必做数={len(musts)}")
            if wk == SPRING and len(musts) > 1:
                errors.append(f"W{wk} {day} 春节周小必做{len(musts)}>1")
        if wk not in HOLIDAY:
            if sat_n < 1 or sat_n > 4 or sun_n < 1 or sun_n > 3:
                warns.append(f"W{wk} 周末块数 六{sat_n} 日{sun_n}")

    # --- 理科练习不得在晚自习 ---
    for s in ("数学", "物理", "化学"):
        for w in subs[s]["weeks"]:
            if w["week"] in HOLIDAY:
                continue
            for t in w.get("weekday") or []:
                if t.get("slot") in ("晚自习",) and t.get("type") != "背诵":
                    errors.append(f"理科晚自习非背诵 {s} W{w['week']}")
                if s in ("数学",) and t.get("slot") == "晚自习":
                    errors.append(f"数学不应占用晚自习 W{w['week']}")

    # --- answers ---
    ans_hits = []
    for s, d in subs.items():
        for path, val in walk_strings(d):
            if ANSWER_RE.search(val) and not NEG_ANSWER_RE.search(val):
                ans_hits.append(f"{s}{path}: {val[:80]}")
    errors.extend("疑似答案 " + h for h in ans_hits)

    # --- week alignment ---
    cal_weeks = {w["week"]: w for w in cal["weeks"]}
    for s, d in subs.items():
        weeks = [w["week"] for w in d["weeks"]]
        if weeks != list(range(1, 30)):
            errors.append(f"{s} 周次不完整: {weeks}")
        for w in d["weeks"]:
            cw = cal_weeks[w["week"]]
            if w.get("monday") != cw["monday"]:
                errors.append(f"{s} W{w['week']} monday {w.get('monday')} != calendar {cw['monday']}")
            if w.get("phase") != cw["phase"]:
                errors.append(f"{s} W{w['week']} phase {w.get('phase')} != calendar {cw['phase']}")

    # --- holiday labels ---
    for s, w, t in iter_tasks(subs):
        if w["week"] in HOLIDAY and "预计" not in (t.get("task") or "") and "预计" not in (w.get("goal") or "") and "预计" not in (w.get("note") or ""):
            warns.append(f"假期未标预计 {s} W{w['week']} {t.get('day')}")

    print("=" * 60)
    print(f"冲突(非晚自习同格多科/多条): {collisions}")
    print(f"错误数: {len(errors)}  警告数: {len(warns)}")
    for e in errors:
        print("ERR", e)
    for e in warns[:40]:
        print("WARN", e)
    if len(warns) > 40:
        print(f"... {len(warns)-40} more warns")

    # summary grid week 1 and week 12
    def grid(wk):
        print(f"\n----- 第{wk}周格子 -----")
        cells = defaultdict(list)
        for s, d in subs.items():
            w = next(x for x in d["weeks"] if x["week"] == wk)
            for t in (w.get("weekday") or []) + (w.get("weekend") or []):
                slot = t.get("slot") or "周末"
                mark = "必做" if is_must(t.get("task") or "") else "可选"
                cells[(t["day"], slot)].append(f"{s}{t['min']}{t['type']}{mark}")
        for day in DAYS:
            slots = []
            for sl in ["午间", "傍晚", "夜间", "晚自习", "周末"]:
                if cells.get((day, sl)):
                    slots.append(f"{sl}:" + ",".join(cells[(day, sl)]))
            if slots:
                print(f"  {day} " + " | ".join(slots))

    grid(1)
    grid(2)
    grid(3)
    grid(11)
    grid(12)
    grid(26)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
