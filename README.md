# PikaEngine

面向多场景内容与信号流水线的 Harness。当前重点场景是小红书：采集、分析、生成、执行、反馈全链路可运行，同时把 provider 失败收敛为结构化状态。

## 当前小红书链路

- `core/langgraph/tools/signal_gateway.py`：按 provider 顺序拉取信源，产出 `provider_trace / signal_summary / failure_state / action_required / degraded`
- `core/langgraph/tools/web_access.py`：浏览器访问层，默认 `playwright_persistent`，兼容旧 `cdp_http`
- `core/langgraph/tools/xhs_cli_provider.py`：接入 `xhs-cli`，保留 `verification_required / verify_type / verify_uuid`
- `core/langgraph/nodes/acquire.py`：采集阶段，信源为空时退回 seed topic
- `core/langgraph/nodes/execute.py`：执行阶段，浏览器不可用时落本地草稿

## 环境要求

- Python 3.11+
- Chromium 或 Chrome
- 可选：`bb-browser`
- 可选：`xhs-cli`

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install chromium
```

`xhs-cli` 有两种接入方式，二选一：

```bash
python -m pip install -e /path/to/xhs-cli
```

或在 `.env` 里设置：

```bash
XHS_CLI_MODULE_PATH=/absolute/path/to/xhs-cli
```

如果要启用公开数据 provider，再安装：

```bash
npm install -g bb-browser
```

## 环境变量

复制示例配置：

```bash
cp .env.example .env
```

关键变量：

```bash
XHS_BROWSER_BACKEND=playwright_persistent
XHS_PLAYWRIGHT_USER_DATA_DIR=~/.pikaengine/playwright/xiaohongshu
XHS_PLAYWRIGHT_HEADLESS=false
XHS_PLAYWRIGHT_CHANNEL=chrome
XHS_BROWSER_STARTUP_TIMEOUT=30000
XHS_BROWSER_ACTION_TIMEOUT=15000
XHS_BROWSER_NAVIGATION_TIMEOUT=30000
DAILYHOT_API_BASE=http://localhost:6688
XHS_CLI_MODULE_PATH=
```

## Scene 配置

跨机运行时主要看 `config/scenes.example.yaml` 里的这些字段：

- `provider_order`
- `browser_backend`
- `user_data_dir`
- `playwright_channel`
- `headless`
- `startup_timeout_ms`
- `action_timeout_ms`
- `navigation_timeout_ms`
- `dailyhot_api_base`

小红书默认 provider 顺序：

1. `xhs_cli_search` / `xhs_cli_feed`
2. `bb_search` / `bb_feed`
3. `browser_search` / `browser_feed`
4. `hosted_cross_platform`

## 首次登录 Playwright 持久化 profile

首次登录需要把浏览器 profile 建起来并保留登录态：

```bash
python - <<'PY'
from core.langgraph.tools.web_access import browser_open_tab

config = {
    "browser_backend": "playwright_persistent",
    "user_data_dir": "~/.pikaengine/playwright/xiaohongshu",
    "playwright_channel": "chrome",
    "headless": False,
}

target = browser_open_tab(
    "https://www.xiaohongshu.com/explore",
    wait_seconds=600,
    config=config,
)
print("target:", target)
input("完成登录后按回车结束...")
PY
```

登录完成后，cookie 会保存在 `XHS_PLAYWRIGHT_USER_DATA_DIR` 指向的目录里。后续 `browser_status()` 会直接复用这个 profile。

## Provider 检查

```bash
python - <<'PY'
from core.langgraph.tools.bb_browser import bb_browser_provider_status
from core.langgraph.tools.web_access import browser_status
from core.langgraph.tools.xhs_cli_provider import xhs_cli_status

config = {
    "browser_backend": "playwright_persistent",
    "user_data_dir": "~/.pikaengine/playwright/xiaohongshu",
    "playwright_channel": "chrome",
    "headless": False,
}

print("browser:", browser_status(config))
print("xhs-cli:", xhs_cli_status())
print("bb-browser:", bb_browser_provider_status("xiaohongshu/search AI工具"))
PY
```

期望状态：

- browser provider：`success`
- xhs-cli：`success` 或明确的 `auth_expired / verification_required`
- bb-browser：`success` 或明确的 `unavailable / timeout / error`

## 运行

### 另一台电脑上的最短 dry-run

```bash
python run.py --scene xiaohongshu_trending --config config/scenes.example.yaml --dry-run -v
```

### 主场景执行

```bash
python run.py --scene xiaohongshu --config config/scenes.example.yaml -v
```

### 指定 run_id

```bash
python run.py --scene xiaohongshu_trending --run-id demo-xhs-001 --dry-run
```

## 运行产物

每次执行会在 `data/runs/<run_id>/` 下生成：

- `run.json`
- `events.jsonl`
- `artifacts/acquire.json`
- `artifacts/feedback.json`

排查时优先看：

- `run.json.status`
- `run.json.action_required`
- `artifacts/feedback.json.failure_state`
- `artifacts/feedback.json.provider_trace`

## 常见状态与动作

### `unavailable`

表示 provider 没装好、浏览器没起来，或配置不可用。

- browser provider：检查 `playwright` 安装、`playwright install chromium`、profile 路径、浏览器锁文件
- xhs-cli：安装依赖或配置 `XHS_CLI_MODULE_PATH`
- bb-browser：安装全局命令并确认可执行

### `auth_expired`

表示登录态失效。

- browser provider：用持久化 profile 手动重新登录小红书
- xhs-cli：重新执行 `xhs login`

### `verification_required`

表示小红书平台要求额外验证。当前 `xhs-cli` 会把 `verify_type` 和 `verify_uuid` 写进状态。

- 按平台提示完成验证
- 重新执行 `xhs login --qrcode`
- 再次运行场景

### `timeout`

表示 provider 超时。

- 稍后重试
- 减少 `max_notes` / `max_per_keyword`
- 提高 `startup_timeout_ms` 或 `navigation_timeout_ms`

### `degraded=true`

表示链路可继续跑，但使用了降级策略，例如：

- 某些 provider 失败后切换到后续 provider
- 外部信源全部为空后退回 seed topic
- 浏览器发布失败后改存本地草稿

## 面试演示路径

推荐顺序：

1. 先跑 `xiaohongshu_trending --dry-run`
2. 展示 `provider_trace`、`failure_state`、`action_required`
3. 展示生成内容和 `data/runs/<run_id>/artifacts/`
4. 再跑 `xiaohongshu` 主场景，展示草稿或发布动作
5. 如遇失败，直接解释是哪一个 provider 失败、系统给了什么动作

演示时重点看这几个文件：

- `data/runs/<run_id>/run.json`
- `data/runs/<run_id>/events.jsonl`
- `data/runs/<run_id>/artifacts/acquire.json`
- `data/runs/<run_id>/artifacts/feedback.json`

## 测试

```bash
python -m pytest tests/test_xhs_cli_provider.py tests/test_browser_providers.py tests/integration/test_xiaohongshu_harness.py
```

## 代码定位

- 浏览器后端选择：`core/langgraph/tools/web_access.py`
- 小红书 provider 聚合：`core/langgraph/tools/signal_gateway.py`
- 小红书浏览器采集：`core/langgraph/tools/xiaohongshu.py`
- 小红书执行节点：`core/langgraph/nodes/execute.py`
- 运行器：`core/runtime/graph_runner.py`
