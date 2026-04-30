# notion-cli — AI 驅動的 Notion 資料庫操作工具

**Plan ID**: `notion-cli-mvp`
**Date**: 2026-04-30
**Mode**: Plan (interactive)
**Owner**: mat@hummingfood.com
**Target dir**: `/Volumes/HF-iMac2015-Storage/Projects/NotionPlugin`

---

## 1. Requirements Summary

開發 `notion-cli` — 一個 Python CLI 工具，讓 AI 代理（Claude Code / Codex / Gemini / 自寫 Python agent）能透過 shell 命令操作指定 Notion workspace 的資料庫。Notion 是團隊（一般人員）寫入需求/任務的入口；AI 透過 CLI 讀取需求、建立／更新 cards、回寫處理進度與留言。

### 已確認決策

| 項目 | 決策 |
|------|------|
| 整合模式 | 純 CLI，AI 跨平台呼叫（stdout JSON） |
| 語言 | Python 3.11+ |
| Notion SDK | `notion-client` (官方 Python SDK) |
| 認證 | 單一內部 workspace + Internal Integration Token |
| Onboarding | `notion-cli init` 互動式 wizard；`notion-cli logout` 清除 |
| Token 儲存 | OS keyring（macOS Keychain / Linux Secret Service），fallback 加密檔 |
| MVP 操作 | Card CRUD、讀寫 card 內文 blocks、comments、全文搜尋 |
| Binary 名稱 | `notion-cli` |
| 發佈 | pipx (`pipx install notion-cli`) |
| CLI 框架 | Typer（Click-based、type-hint 驅動） |
| 輸出 | 預設 JSON（stdout）；`--pretty` 走 rich tables |

### 非目標（明確排除）

- ❌ OAuth / 多 workspace（保留架構接口但不實作）
- ❌ 雙向同步（不做檔案 ↔ Notion sync）
- ❌ 內建 LLM 呼叫（CLI 只負責 Notion 操作；AI 由外部驅動）
- ❌ Web UI / GUI

---

## 2. Acceptance Criteria（可驗證）

### A. CLI 基礎
- [ ] `pipx install -e .` 成功安裝後 `notion-cli --version` 顯示版本號
- [ ] `notion-cli --help` 列出所有子命令並 exit code = 0
- [ ] 在未登入狀態下，任何需要 Notion API 的命令 exit code = 2 並 stderr 提示「請先執行 `notion-cli init`」
- [ ] 所有命令支援 `--json`（預設）與 `--pretty` 兩種輸出
- [ ] 錯誤訊息固定走 stderr，資料固定走 stdout（管線安全）
- [ ] Exit code 規範：`0` 成功 / `1` 使用者錯誤 / `2` 認證錯誤 / `3` API 錯誤 / `4` 找不到資源

### B. Onboarding（init / logout / 認證管理）
- [ ] `notion-cli init` 互動式 wizard：
  1. 顯示 https://www.notion.so/profile/integrations 連結，引導建立 Internal Integration
  2. 以 `getpass` 風格隱藏輸入 token（不寫進 shell history）
  3. 立即打 `/v1/users/me` 驗證 token，失敗時 exit 2 並重來
  4. 列出 integration 目前可看到的 databases（可能為空，提示使用者去 Notion 把 integration 加進 database 的「Connections」）
  5. 讓使用者挑一個當預設 database，並輸入 alias（可空）
  6. token 寫入 OS keyring（service=`notion-cli`, account=`default`），config 寫入 `~/.config/notion-cli/config.toml`
- [ ] `notion-cli init --force` 覆蓋既有設定；不加 `--force` 且已設定時提示「已登入 <integration name>，要覆蓋請加 --force」
- [ ] `notion-cli init --token <t> --database <id> --alias <name>` 非互動模式（給 CI / dotfile 自動化用）
- [ ] `notion-cli logout` 清除：(1) keyring 中的 token、(2) config.toml、(3) `~/.cache/notion-cli/` 整個目錄
- [ ] `notion-cli logout --keep-config` 只清 token，保留 config（換 token 用）
- [ ] `notion-cli logout` 在未登入狀態下 idempotent（exit 0，stderr 提示「nothing to do」）
- [ ] `notion-cli auth verify` 印出 integration 名稱與已授權 databases，exit 0
- [ ] `notion-cli auth status` 印出當前 token 來源（keyring / env / flag）與 config 路徑，不曝露 token 本身

### C. 設定與 database alias 管理
- [ ] `~/.config/notion-cli/config.toml` 支援 `[default]` 與 `[databases.<alias>]` sections
- [ ] `notion-cli database add <alias> --id <db_id>` 新增 alias
- [ ] `notion-cli database ls` 列出所有 alias（連同 id）
- [ ] `notion-cli database rm <alias>` 移除 alias
- [ ] 命令支援 `--database <id_or_alias>`，未指定則用 `NOTION_DATABASE_ID` env，再退回 config `[default].database`

### D. Card CRUD
- [ ] `notion-cli card list --database <id_or_alias> [--filter ...] [--sort ...]` 回傳 JSON array
- [ ] `notion-cli card get <id>` 回傳單張 card 的 properties（不含內文 blocks）
- [ ] `notion-cli card create --database <id> --title "..." [--set Prop=Val]...` 建立後 stdout 回傳新 card id 與 url
- [ ] `notion-cli card update <id> [--set Prop=Val]... [--title "..."]` 套用後 stdout 回傳更新後 properties
- [ ] `notion-cli card archive <id>` 將 card 設為 archived，再次執行 idempotent
- [ ] `notion-cli card archive <id>` 預設提示「This will archive (not delete)…」要求 `--yes` 才執行；`NOTION_CLI_FORCE=1` 可全域跳過

### E. Schema-aware property coercion
- [ ] `notion-cli database schema <id_or_alias>` 回傳 properties 清單與型別（含 select / multi_select 的 options）
- [ ] `--set Status=Done` 自動依 schema 將 `Done` 包裝成 `{"select":{"name":"Done"}}`
- [ ] 對未知 property 名稱 exit code = 1 並列出可用名稱
- [ ] 對 select option 不存在時 exit code = 1 並列出可用 options
- [ ] `--set-raw '<json>'` 提供 escape hatch，繞過 coercion 直接送 raw payload
- [ ] Schema 快取於 `~/.cache/notion-cli/schema/<db_id>.json`，TTL 預設 1 小時，可用 `--no-cache` 強制重抓

### F. Blocks（card 內文）
- [ ] `notion-cli card read <id> [--format markdown|json]` 預設 markdown
- [ ] `notion-cli card append <id> --markdown "..."` 或 `--from-file path.md` 將 markdown 轉 blocks 後 append
- [ ] 支援的 block 型別至少：paragraph / heading_1-3 / bulleted_list_item / numbered_list_item / to_do / code / quote / divider
- [ ] 非支援的 block 型別在 read 時降級為 plain text，append 時忽略並 stderr 警告

### G. Comments & Search
- [ ] `notion-cli comment add <card_id> --text "..."` 在 card 上新增 comment
- [ ] `notion-cli comment list <card_id>` 列出該 card 的 comments
- [ ] `notion-cli search "<query>" [--type page|database] [--limit N]` 走 Notion `search` API

### H. 觀測 & 除錯
- [ ] `--verbose` flag 將 HTTP request/response 寫到 stderr（token 永遠遮罩成 `secret_***`）
- [ ] `NOTION_CLI_LOG=debug` env var 啟用 debug log
- [ ] 所有 Notion API 錯誤訊息（含 request_id）原樣轉出

### I. 測試
- [ ] Unit test 覆蓋率 ≥ 80%
- [ ] Integration test 對 staging workspace 跑完 init → card lifecycle → logout 流程
- [ ] CI 設定 ruff + mypy + pytest，三者 PR 必須綠才能 merge

### J. 文件
- [ ] `README.md` 含安裝、5 分鐘 quickstart（含 `notion-cli init`）、子命令一覽
- [ ] `docs/ai-usage.md` 給 AI 代理閱讀的呼叫指南，含 JSON 輸出範例
- [ ] 每個子命令 `--help` 包含至少一個範例

---

## 3. 專案結構

```
NotionPlugin/
├── pyproject.toml              # PEP 621 metadata + entry point
├── README.md
├── .gitignore
├── .python-version             # 3.11
├── ruff.toml
├── mypy.ini
├── src/notion_cli/
│   ├── __init__.py             # __version__
│   ├── __main__.py             # python -m notion_cli
│   ├── cli.py                  # Typer root app
│   ├── config.py               # toml read/write
│   ├── credentials.py          # keyring wrapper + fallback
│   ├── client.py               # NotionClient wrapper（auth、retry）
│   ├── output.py               # JSON / rich pretty formatters
│   ├── errors.py               # CLIError → exit code mapping
│   ├── logging.py              # verbose / debug 設定
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── init.py             # notion-cli init wizard
│   │   ├── logout.py           # notion-cli logout
│   │   ├── auth.py             # auth verify / status
│   │   ├── database.py         # database schema / add / ls / rm
│   │   ├── card.py             # card list/get/create/update/archive
│   │   ├── blocks.py           # card read / append
│   │   ├── comments.py         # comment add / list
│   │   └── search.py           # search
│   └── notion/
│       ├── __init__.py
│       ├── schema.py           # schema 抓取 + 快取
│       ├── coercion.py         # property value 強制轉型
│       └── markdown.py         # blocks ↔ markdown converter
├── tests/
│   ├── conftest.py             # fixtures, vcrpy
│   ├── unit/
│   │   ├── test_credentials.py
│   │   ├── test_config.py
│   │   ├── test_coercion.py
│   │   ├── test_markdown.py
│   │   ├── test_output.py
│   │   └── test_schema_cache.py
│   ├── integration/
│   │   ├── test_init_logout.py
│   │   ├── test_card_lifecycle.py
│   │   ├── test_blocks.py
│   │   └── test_search.py
│   └── cassettes/              # vcrpy 錄製的 HTTP fixtures
└── docs/
    ├── ai-usage.md
    └── examples/
        ├── claude-code.md
        └── python-agent.md
```

---

## 4. 分階段實作（Phased Plan）

### Phase 1 — Foundation + Onboarding（預估 2 天）
**目標**：可安裝、能跑 `init` → `auth verify` → `logout` 完整生命週期。
**成功標準**：全新環境 `pipx install -e .` → `notion-cli init`（互動）→ `notion-cli auth verify` 通過 → `notion-cli logout` 完全清除。
**測試**：unit（config loader、credentials keyring mock、output formatter、error → exit code）+ integration（init/logout 對 staging workspace）。
**主要檔案**：`pyproject.toml`、`src/notion_cli/{cli,config,credentials,client,output,errors,logging}.py`、`commands/{init,logout,auth}.py`、`tests/unit/test_{config,credentials,output}.py`、`tests/integration/test_init_logout.py`。

### Phase 2 — Database & Card CRUD（預估 2.5 天）
**目標**：完成 acceptance criteria C + D 全部。
**成功標準**：`notion-cli database add/ls/rm`、`card create / get / list / update / archive` 全部通過 integration test。
**測試**：unit（filter/sort 參數解析）+ integration（真實 workspace 一次完整 lifecycle）。
**主要檔案**：`commands/{database,card}.py`、`tests/integration/test_card_lifecycle.py`。

### Phase 3 — Schema-aware coercion（預估 1.5 天）
**目標**：完成 E 全部。
**成功標準**：`--set Status=Done --set Priority=High` 能正確包裝；未知 property/option 給出有用錯誤。
**測試**：unit test 涵蓋每種 property 型別（title / rich_text / number / select / multi_select / status / date / checkbox / relation / people）。
**主要檔案**：`notion/{schema,coercion}.py`、`tests/unit/test_coercion.py`、`tests/unit/test_schema_cache.py`。

### Phase 4 — Blocks & Markdown（預估 2 天）
**目標**：完成 F 全部。
**成功標準**：`card read --format markdown` 與 `card append --markdown` 能 round-trip 還原大多數 block 型別。
**測試**：unit test 對每個 block 型別做 markdown ↔ block 雙向轉換；integration test 走 append → read → 比對。
**主要檔案**：`commands/blocks.py`、`notion/markdown.py`、`tests/unit/test_markdown.py`、`tests/integration/test_blocks.py`。

### Phase 5 — Comments & Search（預估 0.5 天）
**目標**：完成 G 全部。
**成功標準**：comment add/list、search 都能呼叫且輸出正確。
**主要檔案**：`commands/{comments,search}.py`、`tests/integration/test_search.py`。

### Phase 6 — Polish & Docs（預估 1 天）
**目標**：完成 H、J；CI 綠燈；可 publish 到內部 PyPI 或私有 git+http 安裝。
**成功標準**：`docs/ai-usage.md` 可讓 AI 代理直接照做；CI 跑 ruff + mypy + pytest 全綠。
**主要檔案**：`README.md`、`docs/ai-usage.md`、`docs/examples/*`、`.github/workflows/ci.yml`。

**總計**：約 9.5 個工作天（單人）。

---

## 5. 關鍵技術決策

### 5.1 命令設計風格
採用 **resource + verb** 風格（類似 `kubectl`、`gh`）：
```
notion-cli <resource> <verb> [args] [flags]
notion-cli init                                    # 一次性設定
notion-cli card list --database requirements --filter "Status=Todo"
notion-cli card update abc123 --set Status=InProgress --set Assignee=mat@hummingfood.com
notion-cli card append abc123 --markdown "## 處理進度\n- [x] 已釐清需求"
notion-cli logout
```

### 5.2 Token 儲存與安全
1. **首選**：`keyring` 套件存 OS keychain
   - macOS → Keychain
   - Linux → Secret Service / KWallet
   - Windows → Credential Manager
2. **Fallback**（headless server 沒有 keyring backend 時）：寫到 `~/.config/notion-cli/secrets.toml`，自動 chmod 600，並在 stderr 警告
3. **永遠不**把 token 寫進 `config.toml`（config 會被使用者放進 dotfile repo）
4. **Verbose log** 中固定遮罩 token 為 `secret_***`
5. **`logout` 同時清** keyring + config + cache

### 5.3 Property coercion 策略
1. 抓 schema → 知道每個 property 的型別
2. `--set Name=Value` 依型別決定怎麼包裝：
   - `title` / `rich_text` → `{"title":[{"type":"text","text":{"content":"<v>"}}]}`
   - `select` / `status` → 先驗證 option 存在；不存在則 exit 1 列出合法值
   - `multi_select` → 用 `,` 切（`--set Tags=urgent,bug`）
   - `number` → `int(v)` 或 `float(v)`，失敗 exit 1
   - `checkbox` → `true/false/1/0/yes/no` 都接受
   - `date` → 嘗試 `dateutil.parser` 解析
   - `people` / `relation` → 接受 id 或 email/title，自動 lookup
3. 對複雜情況提供 `--set-raw '{...}'` escape hatch

### 5.4 Output contract（與 AI 之間的合約）
**所有命令在預設模式下輸出符合下列契約的 JSON：**
```json
{
  "ok": true,
  "data": { /* 命令結果 */ },
  "meta": { "duration_ms": 234, "request_id": "..." }
}
```
失敗時：
```json
{
  "ok": false,
  "error": {
    "code": "PROPERTY_NOT_FOUND",
    "message": "Property 'Statuss' not found. Available: Status, Priority, Assignee",
    "hint": "Did you mean 'Status'?"
  }
}
```
Exit code 同時反映成功／失敗。AI 可以單純看 exit code 也可以解析 JSON 拿細節。

### 5.5 認證載入優先序（高 → 低）
1. CLI flag（`--token`）
2. Env var（`NOTION_TOKEN`）
3. OS keyring（`notion-cli` service / `default` account）
4. Fallback 加密檔（`~/.config/notion-cli/secrets.toml`）

### 5.6 重試策略
Notion API 有 429（rate limit）；用 `tenacity` 對 429 / 5xx 做指數退避（最多 3 次）。所有請求預設 30 秒 timeout。

---

## 6. Risks & Mitigations

| 風險 | 影響 | 緩解 |
|------|------|------|
| Token 被誤寫進 git / dotfile | 安全外洩 | 預設走 keyring；config.toml 永不放 token；verbose log 遮罩；README 強調 |
| 無 keyring backend 的 headless server | `init` 失敗或退回明文 | 偵測 keyring backend；無則 fallback 到 chmod 600 secrets.toml + stderr 警告；提供 `--token` flag 一次性使用 |
| `init` wizard 列不出 databases（integration 沒被加進任何 page） | 使用者誤以為 token 壞了 | wizard 明確顯示「Token 有效，但目前沒有任何 database 被授權；請到 Notion 該 page 點 Connections 加入 integration，再重新執行 `notion-cli database add`」 |
| `logout` 沒清乾淨（keyring API 有時靜默失敗） | 殘留 credential | logout 後立刻重抓驗證已不存在；不一致則 exit 1 列出殘留位置 |
| Notion 無 hard-delete；archive 不可逆 | 使用者誤以為 archive = delete | `archive` 命令前提示「This will archive (not delete)…」需 `--yes`；`NOTION_CLI_FORCE=1` 可跳過 |
| Schema 快取過期 | `--set Status=NewOption` 報「不存在」但 Notion 已加 | TTL 預設 1 小時；`--no-cache` / `database schema --refresh`；coercion 失敗時自動重抓再試一次 |
| Markdown ↔ blocks 不可能完美 round-trip | AI append 後 read 不一致 | 文件明列「支援」與「不完美支援」block 型別；read 對未支援 block 標 `<!-- unsupported: <type> -->` |
| Notion API 速率限制（每 integration 約 3 req/s） | 大批量操作會被 429 | tenacity 指數退避；`card list` 預設 page size 100；`--rate-limit` 可調 |
| 非英文 select option 解析 | 「進行中 🚧」等 option 出錯 | 不做模糊比對；逐字比對；錯誤訊息列出原樣可用 options |
| Notion SDK breaking change | 升級後跑不起來 | `pyproject.toml` pin minor 版本（`notion-client>=2.2,<3`）；CI 跑 weekly smoke test |
| 整合 token 權限不足 | 命令給出 `object_not_found` 但訊息對使用者沒幫助 | `auth verify` 列出已授權 databases；錯誤訊息附「請在 Notion 把 integration 加入該 page/database」連結 |

---

## 7. Verification Steps

### 開發中持續驗證
```bash
# 安裝（editable）
pipx install -e . --force

# Lint + type
ruff check src/ tests/
mypy src/notion_cli

# Unit
pytest tests/unit -v --cov=notion_cli --cov-report=term-missing

# Integration（需設定測試 workspace 的 token）
NOTION_TEST_TOKEN=secret_xxx NOTION_TEST_DATABASE_ID=xxx \
  pytest tests/integration -v
```

### 完成定義（Phase 6 結束時）
1. 全新環境跑 `pipx install notion-cli` → `notion-cli init` → 5 分鐘內完成第一張 card create
2. `notion-cli logout` 完全清除痕跡，再 `init` 一次能順利重設
3. `docs/ai-usage.md` 給 Claude Code，餵 prompt「請列出 Status=Todo 的 cards 並把 priority 最高那張改成 InProgress」，能直接成功
4. CI 綠：ruff、mypy、pytest 全過

---

## 8. AI 使用契約（給 Claude Code / Codex / Gemini）

`docs/ai-usage.md` 將提供下列模式範例：

```bash
# 0. 第一次（人工）：建立 integration、登入、設 alias
notion-cli init                       # wizard：建 integration → 貼 token → 選 database → 取 alias

# 1. 認證檢查（startup 時跑一次）
notion-cli auth verify

# 2. 取得 schema（讓 AI 知道有哪些 property 與 status options）
notion-cli database schema requirements

# 3. 列出待處理 cards
notion-cli card list --database requirements \
  --filter 'Status=Todo' --sort '-CreatedAt' --limit 10

# 4. 讀取單張 card 內文
notion-cli card read abc123 --format markdown

# 5. 改狀態 + 加處理紀錄
notion-cli card update abc123 --set Status=InProgress --set Assignee=mat
notion-cli card append abc123 --markdown "## $(date +%F) 進度\n- [x] 已分析需求"

# 6. 留言通知人類
notion-cli comment add abc123 --text "已完成第一階段，請 review"
```

---

## 9. Open Questions / Future Work

- ⏳ **OAuth 多 workspace** — `client.py` 預留 token provider 介面
- ⏳ **MCP server wrapper** — 同一份核心套件可額外用 `mcp` package 包成 MCP server
- ⏳ **Webhook listener** — 「Notion 寫入新需求 → 觸發 AI 處理」需要 webhook 或 polling
- ⏳ **多 profile 切換** — `notion-cli init --profile work` / `--profile personal`，目前只有 `default`
- ⏳ **互動式 TUI** — 用 textual 包裝給人類用

---

## 10. 下一步

計畫已涵蓋 onboarding（`init`）、認證（`auth verify` / `auth status`）、登出（`logout` / `logout --keep-config`）、token 安全儲存（keyring + fallback）。

執行路徑建議：以本計畫為輸入交給 ralph 模式自動執行，從 Phase 1 開始實作直到 Phase 6 完工。

---

*本計畫遵循 CLAUDE.md 中的開發哲學（漸進式進步、測試驅動、簡潔優於聰明）與技術標準。*
