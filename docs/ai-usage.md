# notion-cli — AI 使用指南

這份文件給 AI 代理（Claude Code / Codex / Gemini / 自寫 Python agent）閱讀。

## 輸出契約

每個命令輸出一個 JSON 物件。**請永遠用 exit code 判斷成功 / 失敗**，再解析 JSON 取細節。

| Exit code | 意義 | JSON 走 |
|---|---|---|
| 0 | 成功 | stdout |
| 1 | 使用者錯誤（USER_ERROR） | stderr |
| 2 | 認證錯誤（AUTH_ERROR / INVALID_TOKEN） | stderr |
| 3 | Notion API 錯誤（API_ERROR） | stderr |
| 4 | 找不到資源（NOT_FOUND） | stderr |

```json
// 成功
{ "ok": true, "data": { ... }, "meta": { "duration_ms": 234 } }

// 失敗
{ "ok": false, "error": { "code": "<UPPER_SNAKE>", "message": "...", "hint": "..." } }
```

## 推薦使用順序

```bash
# 1. 啟動時驗證可用
notion-cli auth verify
# 失敗（exit 2）→ 通知使用者跑 `notion-cli init`

# 2. 取得 schema，學會有哪些 property + status options
notion-cli database schema requirements
# 用結果指導後續 --set Status=<options 中之一>

# 3. 找到工作項目
notion-cli card list --database requirements \
  --filter-json '{"property":"Status","select":{"equals":"Todo"}}' \
  --sort '-CreatedAt' \
  --limit 10

# 4. 讀單張 card 內文
notion-cli card read <card_id>            # 預設 markdown
notion-cli card read <card_id> --format json   # 原始 blocks

# 5. 改狀態 + 加處理紀錄
notion-cli card update <card_id> --set Status=InProgress --set Assignee=mat@hummingfood.com
notion-cli card append <card_id> --markdown "## $(date +%F) 進度\n- [x] 已釐清需求"

# 6. 留言告知人類
notion-cli comment add <card_id> --text "已完成第一階段，請 review"
```

## 樣式範例 — 完整 JSON

### auth verify 成功
```json
{
  "ok": true,
  "data": {
    "integration_name": "Internal Integration",
    "bot_id": "abc-123",
    "databases": [
      { "id": "11111111-1111-1111-1111-111111111111", "title": "Requirements" }
    ]
  }
}
```

### database schema
```json
{
  "ok": true,
  "data": {
    "id": "11111111-1111-1111-1111-111111111111",
    "title": "Requirements",
    "properties": [
      { "name": "Name", "type": "title" },
      { "name": "Status", "type": "status", "options": ["Todo", "InProgress", "Done"] },
      { "name": "Priority", "type": "select", "options": ["Low", "Med", "High"] }
    ]
  }
}
```

### card list
```json
{
  "ok": true,
  "data": {
    "results": [
      {
        "id": "page-id",
        "url": "https://notion.so/...",
        "title": "Implement webhook listener",
        "archived": false,
        "properties": { /* full Notion properties payload */ }
      }
    ],
    "count": 1
  }
}
```

### card update
```json
{
  "ok": true,
  "data": {
    "id": "page-id",
    "url": "https://notion.so/...",
    "properties": { /* updated property payload */ }
  }
}
```

### card archive（已 archive 是 idempotent）
```json
{ "ok": true, "data": { "id": "page-id", "archived": true, "already": true } }
```

### Error envelope（INVALID_TOKEN）
```json
{
  "ok": false,
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Notion rejected the token (401 unauthorized).",
    "hint": "Check the integration token; run `notion-cli init --force` to reset."
  }
}
```

## --set 屬性轉型對照

`--set Prop=Value` 會依 schema 自動轉成 Notion 期望的 payload：

| Schema type | 範例輸入 | 轉換結果 |
|---|---|---|
| `title` | `--title "Hi"` | `{"title":[{"text":{"content":"Hi"}}]}` |
| `rich_text` | `--set Notes=Hello` | `{"rich_text":[{"text":{"content":"Hello"}}]}` |
| `number` | `--set Score=42` | `{"number":42}` |
| `select` | `--set Priority=High` | `{"select":{"name":"High"}}`（option 必須存在） |
| `multi_select` | `--set Tags=bug,urgent` | `{"multi_select":[{"name":"bug"},{"name":"urgent"}]}` |
| `status` | `--set Status=Done` | `{"status":{"name":"Done"}}` |
| `checkbox` | `--set Done=true` / `1` / `yes` | `{"checkbox":true}` |
| `date` | `--set Due=2025-12-31` | `{"date":{"start":"2025-12-31T00:00:00"}}` |
| `url` / `email` / `phone_number` | `--set Link=https://x.com` | `{"url":"https://x.com"}` |
| `people` | `--set Owners=user_id1,user_id2` | `{"people":[{"id":"user_id1"},...]}` |
| `relation` | `--set Related=page_id1,page_id2` | `{"relation":[{"id":"page_id1"},...]}` |

不確定 schema 結構時用 `--set-raw '{"<Prop>":{"select":{"name":"X"}}}'` 直接送 raw JSON。

## 錯誤處理建議（給 AI agent）

```python
import subprocess, json

def call(args):
    r = subprocess.run(["notion-cli", *args], capture_output=True, text=True)
    payload_text = r.stdout if r.returncode == 0 else r.stderr
    payload = json.loads(payload_text)
    return r.returncode, payload

code, p = call(["card", "update", card_id, "--set", "Status=Done"])
if code == 2:
    raise SystemExit("Notion token invalid — please run `notion-cli init`")
if code == 1 and p["error"]["code"] == "ALIAS_EXISTS":
    # ...
if code == 0:
    return p["data"]
```

詳細範例：[`docs/examples/claude-code.md`](examples/claude-code.md)。
