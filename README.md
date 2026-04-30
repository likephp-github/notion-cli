# notion-cli — AI 代理操作 Notion 的標準工具

> **如果你是 AI agent**：請完整讀完本文件後再開始操作。本文件是「使用 notion-cli 的合約」，目標是讓你不需要再去看別的文件就能完成安裝、設定、CRUD Notion cards、寫進度紀錄、留言、搜尋。
>
> **如果你是人類使用者**：把這個專案路徑或本檔案內容丟給你慣用的 AI（Claude Code / Codex / Gemini / Cursor），告訴它「請依照 README 幫我安裝並使用 notion-cli」即可。

---

## 0. 快速判斷你能否使用

```bash
# 必要先決條件
python3 --version    # 必須 >= 3.11
pip3 --version       # 任何版本即可
```

若 Python < 3.11，請先升級：macOS `brew install python@3.13`；Ubuntu `apt install python3.13-venv`。

---

## 1. 安裝（給 AI 的決策樹）

```
有 pipx？ ──Yes──→  pipx install -e .          ← 推薦（隔離 venv、全域 binary）
   │
   No
   ↓
能用 venv？ ──Yes──→  python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
   │                  之後所有 notion-cli 都改叫 .venv/bin/notion-cli
   No
   ↓
最後手段：pip3 install --user -e .   （會污染 user site-packages，不推薦）
```

**從這個 repo 安裝時的標準流程（給 AI 直接執行）：**

```bash
cd /path/to/NotionPlugin
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
.venv/bin/notion-cli --version    # 預期輸出: 0.1.0
```

若 `--version` 輸出 `0.1.0` 即代表安裝成功，繼續下一步。

---

## 2. 首次設定（init 流程）

### 2.1 你需要一個 Notion Internal Integration Token

**這一步必須請使用者完成，AI 無法代勞：**

1. 開瀏覽器到 <https://www.notion.so/profile/integrations>
2. 點 `+ New integration`，給個名字（例如 `My AI Agent`），選對應的 workspace
3. 建立後複製 `Internal Integration Token`（格式 `secret_...` 或 `ntn_...`）
4. 開啟使用者要操作的 Notion database 頁面，右上角 `⋯` → `Connections` → 加入剛建立的 integration

### 2.2 把 token 寫進 notion-cli

**互動模式（推薦給人類）：**
```bash
notion-cli init
```
Wizard 會：要求貼 token（隱藏輸入）→ 打 `/v1/users/me` 驗證 → 列出 integration 已被授權的 databases → 讓使用者挑預設 database 並取 alias → 把 token 存進 OS keyring，把 config 寫到 `~/.config/notion-cli/config.toml`。

**非互動模式（給 AI / CI 用）：**
```bash
notion-cli init \
  --token "<TOKEN>" \
  --database "<DATABASE_UUID>" \
  --alias requirements
```

> AI 注意：**永遠不要把 token 寫進 commit、log、或對使用者顯示完整 token**。如果使用者把 token 貼在 chat 裡，提醒他們這個 token 仍要保密。

### 2.3 驗證設定成功

```bash
notion-cli auth verify
```

成功回傳 (exit 0)：
```json
{
  "ok": true,
  "data": {
    "integration_name": "My AI Agent",
    "bot_id": "abc-123",
    "databases": [{ "id": "11111111-...", "title": "Requirements" }]
  }
}
```

若 `databases` 是空陣列 → token 有效但沒有 database 被授權 → 提醒使用者去該 database 頁面 `Connections` 加入 integration。

### 2.4 解析優先序（給知道自己在做什麼的 agent）

**Token 解析（從高到低）：**
1. CLI 全域旗標 `--token <T>`（覆寫一次性）
2. 環境變數 `NOTION_TOKEN`
3. OS keyring（`init` 時寫入）
4. Fallback 加密檔 `~/.config/notion-cli/secrets.toml`

**Database 解析（命令吃 `--database` 時）：**
1. CLI 旗標 `--database <UUID 或 alias>`
2. 環境變數 `NOTION_DATABASE_ID`（只在 `--database` 沒給時生效）
3. config 檔的 `[default].database`

例：CI 環境想跑而不污染 keyring：
```bash
NOTION_TOKEN=secret_xxx NOTION_DATABASE_ID=11111111-... \
  notion-cli card list --limit 5
```

### 2.5 人類觀看 vs AI 解析

預設輸出是 **緊湊單行 JSON**（給 AI 解析快、給管線用）。

人類想看的時候加 `--pretty`：

```bash
notion-cli --pretty auth status     # 縮排 + 顏色（用 rich 渲染）
notion-cli auth status              # AI 預設模式：壓縮 JSON
```

`--pretty` 跟 `--json`（預設）只影響顯示，**回傳的資料完全相同**。AI agent 不需要也不應該用 `--pretty`。

---

## 3. 輸出契約（AI 解析的合約）

**所有命令的輸出都符合下列三條規則。AI 永遠依此判斷成功失敗、再解析資料：**

### 3.1 規則一 — exit code 是真相來源

| Exit | 意義 | 對應錯誤碼前綴 |
|---:|---|---|
| 0 | 成功 | — |
| 1 | 使用者錯誤（參數錯、要 `--yes` 沒加、UUID 格式錯…） | `USER_ERROR`, `ALREADY_CONFIGURED`, `CONFIRM_REQUIRED` |
| 2 | 認證錯誤（token 無效、過期、缺失） | `AUTH_ERROR`, `INVALID_TOKEN` |
| 3 | Notion API 錯誤（5xx、限流） | `API_ERROR` |
| 4 | 找不到資源（page/database/block id 不存在或沒權限） | `NOT_FOUND` |

### 3.2 規則二 — 成功 → stdout 一個 JSON 物件

```json
{ "ok": true, "data": { /* 命令輸出 */ }, "meta": { "duration_ms": 234 } }
```

### 3.3 規則三 — 失敗 → stderr 一個 JSON 物件

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

### 3.4 標準解析模板（Python）

```python
import json, subprocess

def call(*args):
    r = subprocess.run(["notion-cli", *args], capture_output=True, text=True)
    payload = json.loads(r.stdout if r.returncode == 0 else r.stderr)
    return r.returncode, payload

code, p = call("card", "list", "--database", "requirements", "--limit", "5")
if code == 0:
    cards = p["data"]["results"]
elif code == 2:
    raise SystemExit("Token invalid; ask user to run `notion-cli init`")
elif code == 4:
    raise SystemExit("Database/card not found")
else:
    raise SystemExit(f"notion-cli failed: {p['error']}")
```

### 3.5 標準解析模板（Bash）

```bash
out=$(notion-cli card list --database requirements --limit 5)
ec=$?
if [ $ec -eq 0 ]; then
  echo "$out" | jq '.data.results'
else
  echo "$out" >&2
  exit $ec
fi
```

---

## 4. 全部命令一覽（含範例與輸出 schema）

### 4.1 設定 / 認證

| 命令 | 用途 |
|---|---|
| `notion-cli init [--token T --database UUID --alias A] [--force]` | 設定 token + 預設 database |
| `notion-cli logout [--keep-config]` | 清除 keyring + config + cache（idempotent） |
| `notion-cli auth verify` | 驗 token 並列出已授權 databases |
| `notion-cli auth status` | 不曝露 token 的設定狀態 |

`auth status` 輸出範例：
```json
{ "ok": true, "data": {
  "configured": true,
  "token_source": "keyring",
  "config_path": "/Users/x/.config/notion-cli/config.toml",
  "default_database": "11111111-..."
}}
```

### 4.2 Database alias 管理

```bash
notion-cli database add <alias> --id <UUID> [--force]
notion-cli database ls
notion-cli database rm <alias>             # idempotent
notion-cli database schema <alias|UUID> [--no-cache | --refresh]
```

`database schema` 輸出範例（這是 AI 在 `--set` 之前必看的東西）：
```json
{ "ok": true, "data": {
  "id": "11111111-...",
  "title": "Requirements",
  "properties": [
    { "name": "Name",     "type": "title" },
    { "name": "Status",   "type": "status",  "options": ["Todo","InProgress","Done"] },
    { "name": "Priority", "type": "select",  "options": ["Low","Med","High"] },
    { "name": "Tags",     "type": "multi_select", "options": ["bug","urgent"] },
    { "name": "Due",      "type": "date" },
    { "name": "Done",     "type": "checkbox" }
  ]
}}
```

### 4.3 Card CRUD

```bash
# 查
notion-cli card list --database <alias|UUID> \
    [--filter-json '<RAW_NOTION_FILTER>'] \
    [--sort 'Priority,-CreatedAt'] \
    [--limit 100]

# 取一張
notion-cli card get <CARD_ID>

# 建
notion-cli card create --database <alias|UUID> \
    --title "...." \
    [--set Prop=Value]... \
    [--set-raw '<RAW_PROPERTIES_JSON>']

# 改
notion-cli card update <CARD_ID> \
    [--title "..."] \
    [--set Prop=Value]... \
    [--set-raw '<RAW_PROPERTIES_JSON>']

# 封存（不可逆，必須加 --yes 或 NOTION_CLI_FORCE=1）
notion-cli card archive <CARD_ID> --yes
```

`card list` 輸出：
```json
{ "ok": true, "data": {
  "results": [{
    "id": "abc-...",
    "url": "https://notion.so/...",
    "title": "Implement webhook listener",
    "archived": false,
    "properties": { /* 完整 Notion properties payload */ }
  }],
  "count": 1
}}
```

### 4.4 `--set Prop=Value` 自動轉型表

| Schema type | 範例 | 轉換結果 |
|---|---|---|
| `title` | `--title "Hi"` | `{"title":[{"text":{"content":"Hi"}}]}` |
| `rich_text` | `--set Notes=Hello` | `{"rich_text":[{"text":{"content":"Hello"}}]}` |
| `number` | `--set Score=42` | `{"number":42}` |
| `select` | `--set Priority=High` | `{"select":{"name":"High"}}` ← option 必須存在 |
| `multi_select` | `--set Tags=bug,urgent` | `{"multi_select":[{"name":"bug"},{"name":"urgent"}]}` |
| `status` | `--set Status=Done` | `{"status":{"name":"Done"}}` ← option 必須存在 |
| `checkbox` | `--set Done=true` / `1` / `yes` | `{"checkbox":true}` |
| `date` | `--set Due=2025-12-31` | `{"date":{"start":"2025-12-31T00:00:00"}}` |
| `url` / `email` / `phone_number` | `--set Link=https://x.com` | `{"url":"https://x.com"}` |
| `people` | `--set Owners=user_id1,user_id2` | `{"people":[{"id":"user_id1"},{"id":"user_id2"}]}` |
| `relation` | `--set Related=page_id1,page_id2` | `{"relation":[{"id":"page_id1"},{"id":"page_id2"}]}` |

select / multi_select / status 的 option 不存在時 → exit 1 並列出可用 options。

任何超出表格範圍的型別 → 用 `--set-raw '<JSON>'` 直接送 Notion 期望的 raw payload。

### 4.5 Card 內文（blocks）讀寫

```bash
# 讀（預設 markdown，也可 --format json 拿 raw blocks）
notion-cli card read <CARD_ID> [--format markdown|json]

# 寫（兩個來源擇一）
notion-cli card append <CARD_ID> --markdown "## 進度\n- [x] done"
notion-cli card append <CARD_ID> --from-file path/to/note.md
```

支援的 markdown block 型別：`paragraph`、`heading_1-3`、`bulleted_list_item`、`numbered_list_item`、`to_do`（`- [ ]` / `- [x]`）、`code`（含語言）、`quote`（`> `）、`divider`（`---`）。其他型別在 read 時會降級為 `<!-- unsupported: <type> -->` 提示。

### 4.6 Comment & Search

```bash
notion-cli comment add <CARD_ID> --text "..."
notion-cli comment list <CARD_ID>

notion-cli search "query string" [--type page|database] [--limit 50]
```

---

## 5. 標準工作流程（AI 可直接複製）

### 5.1 「處理 Status=Todo 的高優先級任務」

```bash
# 1. 讀 schema（確認 Status options）
notion-cli database schema requirements

# 2. 找符合條件的 cards
notion-cli card list --database requirements --filter-json '{
  "and": [
    {"property":"Status","status":{"equals":"Todo"}},
    {"property":"Priority","select":{"equals":"High"}}
  ]
}' --sort '-CreatedAt' --limit 10

# 3. 取第一張的 id (假設 abc123)，讀內文
notion-cli card read abc123

# 4. 改狀態 + 加處理紀錄
notion-cli card update abc123 --set Status=InProgress --set Assignee=ai-agent
notion-cli card append abc123 --markdown "## $(date -u +%FT%TZ) AI 接手\n- [x] 已分析需求"

# 5. 留言通知人類
notion-cli comment add abc123 --text "AI 已開始處理，請追蹤"
```

### 5.2 「批次匯出 Done 的 cards 到 markdown 檔」

```bash
notion-cli card list --database requirements \
    --filter-json '{"property":"Status","status":{"equals":"Done"}}' \
    --limit 1000 \
    | jq -r '.data.results[].id' \
    | while read id; do
        notion-cli card read "$id" > "exports/$id.md"
      done
```

### 5.3 「建立新 card 並貼初始內文」

```bash
# 建 card 拿 id
ID=$(notion-cli card create --database requirements \
       --title "AI 探索：自動化測試流程" \
       --set Priority=High \
       --set Status=Todo \
     | jq -r '.data.id')

# 貼初始 brief
notion-cli card append "$ID" --from-file briefs/initial.md
echo "Created: $ID"
```

---

## 6. 錯誤處理決策樹（給 AI）

```
exit 2 → token 出問題
   ├── error.code = INVALID_TOKEN  → 告訴使用者 token 失效，建議跑 `notion-cli init --force`
   └── error.code = AUTH_ERROR     → 缺 token，建議跑 `notion-cli init`

exit 4 → 找不到資源
   └── error.code = NOT_FOUND
       ├── 確認 id 拼寫正確
       └── 提醒使用者把 integration 加進該 page/database 的 Connections

exit 1 → 使用者錯誤
   ├── ALREADY_CONFIGURED   → 加 --force 或先 logout
   ├── CONFIRM_REQUIRED     → archive 漏了 --yes
   ├── USER_ERROR (其他)    → 看 message，常見是 --set Status=XXX 的 option 不存在；read message 中列出的合法 options
   └── --set-raw 不是 valid JSON → 修 JSON

exit 3 → Notion API 失敗 (已自動 retry 3 次仍失敗)
   ├── 通常是 5xx 或 429 限流持續
   └── 等幾分鐘再試；用 --verbose 看 request_id 給 Notion support
```

---

## 7. 安全性規範（AI 必讀）

- Token 預設存 OS keyring（macOS Keychain / Linux Secret Service / Windows Credential Manager）
- 無 keyring backend 時 fallback 到 `~/.config/notion-cli/secrets.toml` (chmod 600)
- `~/.config/notion-cli/config.toml` **絕對不會**包含 token，可安全 commit 到 dotfile repo
- `--verbose` 時 log 中所有 `secret_*` / `ntn_*` 自動遮罩為 `secret_***`
- AI 在對使用者回覆時 **絕對不要** 完整顯示 token，只能顯示前 8 碼 + `...`

---

## 8. AI 自我檢查（Self-test）

執行下列序列驗證自己有正常操作能力：

```bash
notion-cli --version                    # 期望 exit 0、stdout 印版本
notion-cli auth status                  # 期望 exit 0；configured=true 才繼續
notion-cli auth verify                  # 期望 exit 0；data.databases 至少一筆
notion-cli database ls                  # 確認有設定 alias
```

任何步驟失敗 → 暫停、回報使用者、不要繼續執行有副作用的命令。

---

## 9. 何時必須詢問使用者（不要自作主張）

| 情境 | 必須先問 |
|---|---|
| 初次設定但沒 token | 「請到 https://www.notion.so/profile/integrations 建立 Internal Integration 並把 token 給我」 |
| `archive` / 任何具破壞性操作 | 「即將 archive `<title>`，確認嗎？」（除非使用者明確授權批次操作） |
| `card list` 結果 > 50 筆要全部處理 | 「找到 N 筆，要全部處理還是先做前 K 筆？」 |
| token 失效 | 「Notion 拒絕了 token，請重新跑 `notion-cli init --force`」 |
| 同名 alias 已存在 | 「alias `<x>` 已經對應 `<old_id>`，要覆蓋嗎？」 |

---

## 10. 開發 / 測試（給維護者）

```bash
.venv/bin/ruff check src/ tests/        # lint
.venv/bin/mypy src/notion_cli           # type
.venv/bin/pytest tests/unit -v          # 137 unit tests

# Integration tests（需要測試用 workspace 與 token）
NOTION_TEST_TOKEN=secret_xxx \
NOTION_TEST_DATABASE_ID=xxx \
  .venv/bin/pytest tests/integration -v
```

完整設計文件：[`.omc/plans/notion-cli-mvp.md`](.omc/plans/notion-cli-mvp.md)。

---

## 11. 已知限制（截至 v0.1.0）

- **不支援 OAuth** — 單一 workspace + Internal Integration only。多 workspace 需求請看 roadmap。
- **不支援雙向同步** — 工具只做命令式呼叫，不維護本地 ↔ Notion 的 sync state。
- **不內建 LLM** — 只負責 Notion 操作，AI 邏輯由外部驅動（這正是設計目標）。
- **archive 是 Notion 的 archive，不是 hard delete** — 在 Notion UI 仍可手動恢復。

---

## 12. Roadmap

- ✅ Phase 1：init / logout / auth
- ✅ Phase 2：database / card CRUD
- ✅ Phase 3：schema-aware property coercion
- ✅ Phase 4：blocks ↔ markdown
- ✅ Phase 5：comments + search
- ✅ Phase 6：docs + CI
- ⏳ OAuth 多 workspace 支援
- ⏳ MCP server wrapper（讓原生 MCP 客戶端直接使用）
- ⏳ Webhook listener（Notion 寫入 → 觸發 AI）
- ⏳ Multi-profile（`notion-cli init --profile work`）

---

*Generated with https://tech.hummingfood.com 🤖 — Co-Authored-By: 🐯likephp🐯 tech@hummingfood.com*
