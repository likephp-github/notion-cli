# Claude Code 使用範例

## 場景：Claude 自動處理 Notion 需求看板

假設 Notion 中有一個 `Requirements` database，欄位：
- `Name` (title)
- `Status` (status: Todo / InProgress / Done)
- `Priority` (select: Low / Med / High)
- `Assignee` (rich_text)

### Prompt 給 Claude Code

> 「請列出 Status=Todo 的 cards 中 Priority=High 的那幾張，把第一張改成 InProgress、Assignee=claude，並在內文加上『開始處理』的時間戳記。」

Claude Code 會展開為：

```bash
# 1. 學 schema（避免猜 status options）
notion-cli database schema requirements

# 2. 找符合條件的 cards
notion-cli card list --database requirements --filter-json '{
  "and": [
    {"property":"Status","status":{"equals":"Todo"}},
    {"property":"Priority","select":{"equals":"High"}}
  ]
}' --limit 5

# 3. 取出第一個 id（假設叫 abc123）
TARGET=abc123

# 4. 改狀態 + assignee
notion-cli card update "$TARGET" \
  --set Status=InProgress \
  --set Assignee=claude

# 5. Append 處理紀錄
notion-cli card append "$TARGET" \
  --markdown "## $(date -u +%FT%TZ) 進度\n- [x] Claude 開始處理"
```

### 把這套包成 Claude Code skill

`.claude/skills/notion-task.md`：

```markdown
---
name: notion-task
description: Pull a Notion task by id, update its status, and write a note.
---

When the user gives me a Notion card id and an action:
1. Run `notion-cli card get <id>` to confirm the card exists.
2. Run `notion-cli card update <id> --set Status=...` for the requested transition.
3. Run `notion-cli card append <id> --markdown "..."` to log what I did.

Always parse exit codes; on AUTH_ERROR (exit 2), tell the user to run `notion-cli init`.
```

### Sub-agent 模式（更穩）

把 CLI 包成 Python helper：

```python
# notion_helper.py
import json, subprocess

class NotionAgent:
    def _run(self, *args):
        r = subprocess.run(["notion-cli", *args], capture_output=True, text=True)
        payload = json.loads(r.stdout if r.returncode == 0 else r.stderr)
        if r.returncode != 0:
            raise RuntimeError(f"notion-cli {args[0]}: {payload['error']}")
        return payload["data"]

    def todos(self, db="requirements", priority=None):
        f = {"property":"Status","status":{"equals":"Todo"}}
        if priority:
            f = {"and":[f, {"property":"Priority","select":{"equals":priority}}]}
        return self._run("card","list","--database",db,"--filter-json",json.dumps(f))

    def take(self, card_id, who):
        self._run("card","update", card_id, "--set", f"Status=InProgress", "--set", f"Assignee={who}")
        self._run("card","append", card_id, "--markdown", f"## Picked up by {who}")
```

Claude / GPT 透過 tool use 呼叫這個 helper 比直接拼 shell command 穩很多。
