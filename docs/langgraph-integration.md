# LangGraph 集成方案 · PikaEngine 编排层设计

## 定位

LangGraph 在 PikaEngine 中不是替代 n8n，而是**补充**：

| 层 | 工具 | 职责 |
|---|---|---|
| **定时调度** | n8n | Cron 触发、简单 ETL、Webhook |
| **智能编排** | LangGraph | 多步推理、状态管理、条件分支、断点续跑、人工审批 |

n8n 负责「什么时候跑」，LangGraph 负责「怎么跑复杂任务」。

---

## 架构总览

```
n8n (Schedule Trigger)
  │
  │  HTTP POST 触发
  ↓
┌──────────────────────────────────────────────────┐
│              LangGraph Engine (Python)             │
│                                                    │
│  ┌────────────────────────────────────────────┐   │
│  │            StateGraph                       │   │
│  │                                             │   │
│  │  START                                      │   │
│  │    ↓                                        │   │
│  │  [acquire]  ← bb-browser / web-access /     │   │
│  │    ↓           AKShare / CCXT               │   │
│  │  [analyze]  ← LLM 分析 + 打分              │   │
│  │    ↓                                        │   │
│  │  [generate] ← GEOFlow AI Engine             │   │
│  │    ↓                                        │   │
│  │  {risk_gate} ← 量化专用：通过/降级/拒绝     │   │
│  │    ↓                                        │   │
│  │  [execute]  ← web-access 发布 /             │   │
│  │    ↓           GEOFlow 入库 / 交易API       │   │
│  │  [feedback] ← 效果数据回收                  │   │
│  │    ↓                                        │   │
│  │   END                                       │   │
│  └────────────────────────────────────────────┘   │
│                                                    │
│  Checkpointer: PostgreSQL (与GEOFlow共用)          │
└──────────────────────────────────────────────────┘
```

---

## 核心设计：状态定义

```python
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph

class PipelineState(TypedDict):
    # 场景标识
    scene: Literal["xiaohongshu", "gallup", "geo", "quant_a_stock", "quant_crypto"]

    # M1 采集
    acquire_config: dict          # 采集配置（数据源、关键词等）
    raw_data: list[dict]          # 采集到的原始数据

    # M2 分析
    analyzed_items: list[dict]    # 分析后的数据（含评分/信号）
    top_items: list[dict]         # 筛选后的 top N

    # M3 生成
    generated_content: list[dict] # 生成的内容/信号

    # M3.5 风控（量化专用）
    risk_check_passed: bool
    risk_adjustments: list[dict]  # 风控调整记录

    # M4 执行
    execution_results: list[dict] # 发布/交易结果

    # M5 反馈
    feedback_data: dict           # 效果数据

    # 流程控制
    error: Optional[str]
    retry_count: int
    requires_human_review: bool
```

---

## 节点实现：与现有工具集成

### acquire 节点 — 三层工具分发

```python
import subprocess
import json

def acquire_node(state: PipelineState) -> dict:
    scene = state["scene"]
    config = state["acquire_config"]

    if scene == "xiaohongshu":
        raw_data = acquire_xiaohongshu(config)
    elif scene in ("quant_a_stock", "quant_crypto"):
        raw_data = acquire_quant(scene, config)
    elif scene in ("geo", "gallup"):
        raw_data = acquire_web(config)

    return {"raw_data": raw_data}


def acquire_xiaohongshu(config: dict) -> list[dict]:
    """三层递进采集"""
    results = []

    # Layer 1: bb-browser 快速抓热榜（公开数据）
    hot_output = subprocess.run(
        ["bb-browser", "site", "xiaohongshu/hot", "--json"],
        capture_output=True, text=True
    )
    hot_topics = json.loads(hot_output.stdout)
    results.extend(hot_topics)

    # Layer 2: web-access CDP 深度采集（需登录态）
    if config.get("deep_scrape"):
        for topic in hot_topics[:config.get("top_n", 5)]:
            # 用 web-access 的 CDP 打开笔记详情
            detail = cdp_fetch_note_detail(topic["url"])
            results.append(detail)

    return results


def cdp_fetch_note_detail(url: str) -> dict:
    """通过 web-access CDP 获取笔记详情（复用Chrome登录态）"""
    import requests
    CDP_BASE = "http://localhost:3456"

    # 新建标签页
    resp = requests.get(f"{CDP_BASE}/new", params={"url": url})
    target_id = resp.json().get("targetId")

    # 等待加载后提取数据
    extract_js = """
    JSON.stringify({
        title: document.querySelector('.title')?.textContent,
        content: document.querySelector('.content')?.textContent,
        likes: document.querySelector('.like-count')?.textContent,
        comments: document.querySelector('.comment-count')?.textContent,
        tags: [...document.querySelectorAll('.tag')].map(t => t.textContent)
    })
    """
    data = requests.post(
        f"{CDP_BASE}/eval", params={"target": target_id},
        data=extract_js
    )

    # 关闭标签页
    requests.get(f"{CDP_BASE}/close", params={"target": target_id})

    return json.loads(data.text)


def acquire_quant(scene: str, config: dict) -> list[dict]:
    """金融数据采集 — 直接调API，不需要浏览器"""
    if scene == "quant_a_stock":
        import akshare as ak
        # 示例：获取个股日线
        df = ak.stock_zh_a_hist(
            symbol=config["symbol"],
            period="daily",
            adjust="qfq"
        )
        return df.tail(config.get("days", 30)).to_dict("records")

    elif scene == "quant_crypto":
        import ccxt
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(
            config["pair"],
            timeframe=config.get("timeframe", "1h"),
            limit=config.get("limit", 100)
        )
        return [{"timestamp": r[0], "o": r[1], "h": r[2],
                 "l": r[3], "c": r[4], "v": r[5]} for r in ohlcv]


def acquire_web(config: dict) -> list[dict]:
    """通用网页采集 — Crawl4AI 或 bb-browser"""
    results = []
    for url in config.get("urls", []):
        output = subprocess.run(
            ["bb-browser", "open", url, "--snapshot", "--json"],
            capture_output=True, text=True
        )
        results.append(json.loads(output.stdout))
    return results
```

### analyze 节点 — LLM 分析

```python
from langchain_openai import ChatOpenAI

def analyze_node(state: PipelineState) -> dict:
    scene = state["scene"]
    raw_data = state["raw_data"]
    llm = ChatOpenAI(model="deepseek-chat")

    if scene == "xiaohongshu":
        # 热点匹配度打分
        prompt = f"""分析以下小红书热门话题，按爆款潜力打分(0-1)：
        {json.dumps(raw_data, ensure_ascii=False)}
        返回JSON数组，每项包含 topic, score, reason"""
        result = llm.invoke(prompt)
        analyzed = json.loads(result.content)
        top = sorted(analyzed, key=lambda x: x["score"], reverse=True)
        return {"analyzed_items": analyzed, "top_items": top[:5]}

    elif scene in ("quant_a_stock", "quant_crypto"):
        # 信号计算（调用朋友的策略模块）
        signals = compute_signals(raw_data, state["acquire_config"])
        return {"analyzed_items": signals, "top_items": signals}

    elif scene == "geo":
        # 关键词 gap 分析
        prompt = f"""分析以下搜索引擎AI回答中的品牌提及情况：
        {json.dumps(raw_data, ensure_ascii=False)}
        找出缺失的关键词机会"""
        result = llm.invoke(prompt)
        return {"analyzed_items": [json.loads(result.content)], "top_items": []}
```

### risk_gate 节点 — 量化风控（条件边）

```python
def risk_gate_node(state: PipelineState) -> dict:
    """M3.5 风控网关 — 仅量化场景触发"""
    signals = state["generated_content"]
    adjustments = []

    for signal in signals:
        # 仓位上限检查
        if signal.get("position_pct", 0) > 0.2:
            adjustments.append({
                "action": "降级",
                "original": signal["position_pct"],
                "adjusted": 0.2,
                "reason": "超过单笔20%仓位上限"
            })
            signal["position_pct"] = 0.2

        # 日亏损检查
        if signal.get("estimated_loss_pct", 0) > 0.03:
            return {
                "risk_check_passed": False,
                "risk_adjustments": [{"action": "拒绝", "reason": "预估亏损超3%"}],
                "requires_human_review": True
            }

    return {
        "risk_check_passed": True,
        "risk_adjustments": adjustments
    }


def should_risk_gate(state: PipelineState) -> str:
    """条件边：是否需要经过风控"""
    if state["scene"] in ("quant_a_stock", "quant_crypto"):
        return "risk_gate"
    return "execute"


def after_risk_gate(state: PipelineState) -> str:
    """风控后条件边"""
    if not state["risk_check_passed"]:
        return "human_review"  # 需要人工确认
    return "execute"
```

### execute 节点 — 多通道执行

```python
def execute_node(state: PipelineState) -> dict:
    scene = state["scene"]
    content = state["generated_content"]
    results = []

    if scene == "xiaohongshu":
        # web-access CDP 发布到小红书
        for item in content:
            result = cdp_publish_xiaohongshu(item)
            results.append(result)

    elif scene == "geo":
        # 写入 GEOFlow 队列（HTTP API）
        for item in content:
            result = push_to_geoflow(item)
            results.append(result)

    elif scene in ("quant_a_stock", "quant_crypto"):
        if state.get("requires_human_review"):
            return {"execution_results": [{"status": "pending_review"}]}
        # 交易执行（需人工确认模式）
        for signal in content:
            result = execute_trade(signal, state["scene"])
            results.append(result)

    return {"execution_results": results}


def cdp_publish_xiaohongshu(content: dict) -> dict:
    """通过 web-access CDP 发布小红书笔记"""
    import requests
    CDP_BASE = "http://localhost:3456"

    # 打开创作者中心
    resp = requests.get(f"{CDP_BASE}/new",
                        params={"url": "https://creator.xiaohongshu.com/publish/publish"})
    target_id = resp.json().get("targetId")

    # 填写标题
    requests.post(f"{CDP_BASE}/eval", params={"target": target_id},
                  data=f'document.querySelector("#title-input").value = {json.dumps(content["title"])}')

    # 填写正文
    requests.post(f"{CDP_BASE}/eval", params={"target": target_id},
                  data=f'document.querySelector(".ql-editor").innerHTML = {json.dumps(content["body"])}')

    # 注意：实际发布建议 requires_human_review: true，人工确认后再点发布
    return {"status": "draft_created", "title": content["title"]}
```

---

## Graph 组装

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

# 构建图
builder = StateGraph(PipelineState)

# 添加节点
builder.add_node("acquire", acquire_node)
builder.add_node("analyze", analyze_node)
builder.add_node("generate", generate_node)       # 调用 GEOFlow AI Engine
builder.add_node("risk_gate", risk_gate_node)
builder.add_node("execute", execute_node)
builder.add_node("feedback", feedback_node)
builder.add_node("human_review", human_review_node)

# 定义边
builder.set_entry_point("acquire")
builder.add_edge("acquire", "analyze")
builder.add_edge("analyze", "generate")

# 条件边：生成后是否需要风控
builder.add_conditional_edges("generate", should_risk_gate, {
    "risk_gate": "risk_gate",
    "execute": "execute"
})

# 条件边：风控后是否需要人工审批
builder.add_conditional_edges("risk_gate", after_risk_gate, {
    "human_review": "human_review",
    "execute": "execute"
})

builder.add_edge("human_review", "execute")  # 人工审批后继续
builder.add_edge("execute", "feedback")
builder.add_edge("feedback", END)

# 编译（PostgreSQL checkpointer，与 GEOFlow 共用数据库）
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://geo_user:geo_password@localhost:5432/geo_system"
)
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["human_review"]  # 人工审批前暂停
)
```

---

## 运行方式

### 方式一：n8n 定时触发

```
n8n Schedule Trigger (每天 8:00/12:00/18:00)
  ↓
HTTP POST → http://localhost:8000/run
  ↓
LangGraph FastAPI Server 接收并执行
```

### 方式二：CLI 直接调用

```bash
# 跑小红书场景
python -m pika_engine.run --scene xiaohongshu --config config/scenes.yaml

# 跑量化场景
python -m pika_engine.run --scene quant_a_stock --config config/scenes.yaml
```

### 方式三：Claude Code 内交互

```
用户：帮我跑一下小红书采集
Claude：调用 LangGraph graph.invoke({scene: "xiaohongshu", ...})
        → acquire (bb-browser 热榜)
        → analyze (LLM 打分)
        → generate (AI 生成内容)
        → execute (web-access 发布草稿)
        → 返回结果
```

---

## 工具层分工

```
┌──────────────────────────────────────────────────────┐
│                    LangGraph 编排层                     │
│         （状态管理、条件分支、重试、人工审批）            │
├──────────────────────────────────────────────────────┤
│                                                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────┐│
│  │ 快速查询层  │ │ 深度采集层  │ │ 金融数据层          ││
│  │ bb-browser │ │ web-access │ │ AKShare/Tushare/   ││
│  │            │ │ CDP        │ │ CCXT               ││
│  │ 103条命令  │ │ 真实Chrome │ │ 原生API            ││
│  │ 公开数据   │ │ 登录态     │ │ 结构化数据          ││
│  │ 毫秒级     │ │ 反爬绕过   │ │ 高频可靠            ││
│  └────────────┘ └────────────┘ └────────────────────┘│
│                                                        │
├──────────────────────────────────────────────────────┤
│  ┌────────────┐ ┌────────────────────────────────────┐│
│  │ AI 生成层  │ │ 执行层                              ││
│  │ GEOFlow    │ │ web-access → 小红书发布             ││
│  │ AI Engine  │ │ GEOFlow   → GEO站点发布            ││
│  │            │ │ CCXT      → 交易执行                ││
│  └────────────┘ └────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

---

## 场景流程图

### 小红书场景

```
[acquire]                    [analyze]              [generate]         [execute]
bb-browser                   LLM 打分               GEOFlow            web-access
xiaohongshu/hot              筛选 Top 5             AI Engine          CDP 发布
    ↓                            ↓                      ↓                  ↓
web-access CDP          匹配领域关键词            生成标题+正文      创建草稿
深度采集笔记详情        输出 top_items            生成标签+配图      → 人工确认后发布
```

### 量化场景

```
[acquire]              [analyze]           [generate]      [risk_gate]        [execute]
AKShare/CCXT           朋友的策略模块       生成交易信号    仓位/亏损检查      API下单
获取行情数据           计算信号             输出买卖建议    通过/降级/拒绝     或人工确认
                                                              ↓
                                                        [human_review]
                                                        暂停等待确认
```

---

## 关键特性利用

### 1. Checkpointing（断点续跑）

采集大量数据时，如果 analyze 节点报错，不需要重新采集：
```python
# 从上次失败的地方恢复
graph.invoke(None, config={"configurable": {"thread_id": "run-123"}})
```

### 2. Human-in-the-loop（人工审批）

量化交易执行前自动暂停：
```python
# interrupt_before=["human_review"] 已在 compile 时配置
# 人工确认后继续：
graph.invoke(
    {"requires_human_review": False},
    config={"configurable": {"thread_id": "run-123"}}
)
```

### 3. 重试机制

```python
from langgraph.graph import RetryPolicy

builder.add_node(
    "acquire",
    acquire_node,
    retry=RetryPolicy(max_attempts=3, backoff_factor=2)
)
```

---

## 依赖安装

```bash
pip install langgraph langchain-openai langchain-core
pip install psycopg2-binary  # PostgreSQL checkpointer
pip install akshare ccxt     # 金融数据
pip install fastapi uvicorn  # API 服务
```

---

## 文件结构（PikaEngine 新增）

```
PikaEngine/
├── core/
│   └── langgraph/
│       ├── __init__.py
│       ├── state.py            # PipelineState 定义
│       ├── graph.py            # StateGraph 组装
│       ├── nodes/
│       │   ├── acquire.py      # M1 采集节点
│       │   ├── analyze.py      # M2 分析节点
│       │   ├── generate.py     # M3 生成节点
│       │   ├── risk_gate.py    # M3.5 风控节点
│       │   ├── execute.py      # M4 执行节点
│       │   └── feedback.py     # M5 反馈节点
│       └── tools/
│           ├── bb_browser.py   # bb-browser 封装
│           ├── web_access.py   # web-access CDP 封装
│           ├── akshare_tool.py # AKShare 封装
│           ├── ccxt_tool.py    # CCXT 封装
│           └── geoflow_api.py  # GEOFlow API 封装
├── api/
│   └── server.py               # FastAPI 入口
└── run.py                       # CLI 入口
```

---

## 参考

- [LangGraph 官方文档](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph 生产部署指南 (2026)](https://use-apify.com/blog/langgraph-agents-production)
- [LangGraph Python 教程 (Real Python)](https://realpython.com/langgraph-python/)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph) — MIT 协议
