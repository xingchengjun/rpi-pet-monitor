# -*- coding: utf-8 -*-
"""test_dsh_parser.py — 离线验证 DSH 待审批解析器。"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pc_bridge"))
from bridge import _dsh_pending_parse  # noqa: E402

lines = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "dsh_session_dump.jsonl"),
             encoding="utf-8", errors="replace").read().splitlines()

# 找一个 ask_user_question 调用及其 result
qline = qresult = qcid = None
for i, ln in enumerate(lines):
    try:
        obj = json.loads(ln)
    except Exception:
        continue
    if obj.get("type") == "tool/call" and (obj.get("data") or {}).get("name") == "ask_user_question":
        if qline is None:
            qline = i
            qcid = (obj.get("data") or {}).get("callId")
    elif obj.get("type") == "tool/result" and qline is not None and qcid and qcid in ln:
        qresult = i
        break
print("ask_user_question call@%s result@%s" % (qline, qresult))
print("问答已答:", _dsh_pending_parse("\n".join(lines[qline:qresult + 1])), "(期望0)")
print("问答挂起:", _dsh_pending_parse("\n".join(lines[qline:qline + 1])), "(期望1)")

# 找一个普通 pwsh 调用，截断（执行中）
pline = None
for i, ln in enumerate(lines):
    try:
        obj = json.loads(ln)
    except Exception:
        continue
    if obj.get("type") == "tool/call" and (obj.get("data") or {}).get("name") == "pwsh":
        pline = i
        break
print("普通pwsh挂起:", _dsh_pending_parse("\n".join(lines[pline:pline + 1])), "(期望0)")
