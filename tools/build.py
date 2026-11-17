# 合并 data/*.json -> data/bundle.js（让 index.html 直接双击打开也能用）
import json,glob,os
os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")
out={"subjects":{}};errs=[]
for f in sorted(glob.glob("data/*.json")):
    try: j=json.load(open(f,encoding="utf-8"))
    except Exception as e: errs.append(f"{f}: {e}");continue
    if f.endswith("calendar.json"): out["calendar"]=j
    else: out["subjects"][j.get("subject",os.path.basename(f)[:-5])]=j
open("data/bundle.js","w",encoding="utf-8").write("window.PLAN="+json.dumps(out,ensure_ascii=False)+";")
print("ok subjects:",list(out["subjects"]),"errors:",errs)
