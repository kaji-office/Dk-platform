import re

with open("TASKS.md", "r", encoding="utf-8") as f:
    text = f.read()

fixes_to_mark = [
    "GAP-E1-1", "GAP-E1-2", "GAP-E2-1", "GAP-E2-2", "GAP-E2-3", "GAP-E2-4", "GAP-E2-5", "GAP-E3-1", "GAP-D7-1"
]
for gap in fixes_to_mark:
    text = re.sub(rf"- \[ \] \*\*\[{gap}\]\*\*", rf"- [x] **[{gap}]**", text)

# Update FIX-12 through FIX-20 rows
text = re.sub(r"\| (FIX-1[2-9]|FIX-20) .*? \| ⏳ Pending \|", lambda m: m.group(0).replace("⏳ Pending", "✅ Done"), text)

with open("TASKS.md", "w", encoding="utf-8") as f:
    f.write(text)
