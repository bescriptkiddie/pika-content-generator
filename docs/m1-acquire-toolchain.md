# M1 采集模块 · 工具选型

## 总览

```
┌──────────────────────────────────────────────────────────┐
│                     PikaEngine 采集层                      │
│                                                            │
│  ┌─────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │ 调度层   │ ──→ │ 编排层       │ ──→ │ 标准化输出   │   │
│  │ n8n/cron │     │ LangGraph    │     │ AcquireResult│   │
│  └─────────┘     └──────┬───────┘     └──────────────┘   │
│                          │                                  │
│         ┌────────────────┼────────────────┐                │
│         ↓                ↓                ↓                │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │ 快速查询   │  │ 深度采集   │  │ 金融数据            │  │
│  │ bb-browser │  │ web-access │  │ AKShare+Tushare    │  │
│  │ 103条命令  │  │ CDP+登录态 │  │ CCXT               │  │
│  │ Crawl4AI   │  │ 反爬绕过   │  │ Dune/Nansen        │  │
│  └────────────┘  └────────────┘  └────────────────────┘  │
└──────────────────────────────────────────────────────────┘

编排层详细设计见 → docs/langgraph-integration.md
```

---

## 一、编排层（调度 + 智能串联）

### 调度：n8n（自托管）

| 属性 | 详情 |
|------|------|
| 用途 | 定时触发、Webhook 入口、简单 ETL |
| 部署 | Docker 自托管，免费无限制 |
| 调度 | 内置 Schedule Trigger + Cron 表达式 |

### 智能编排：LangGraph

| 属性 | 详情 |
|------|------|
| 用途 | 多步推理、状态管理、条件分支、断点续跑、人工审批 |
| 协议 | MIT，完全免费 |
| 特性 | StateGraph + Checkpointing(PostgreSQL) + Human-in-the-loop |
| 集成 | 调用 bb-browser / web-access / AKShare / CCXT / GEOFlow |

**分工**：n8n 管「什么时候跑」，LangGraph 管「怎么跑复杂任务」。

> 详细设计见 [LangGraph 集成方案](langgraph-integration.md)

### 浏览器工具层

| 工具 | 定位 | 使用场景 |
|------|------|---------|
| **bb-browser** | CLI 快刀，103条平台命令 | 热榜、搜索、公开数据，毫秒级 |
| **web-access** | CDP 代理，复用真实 Chrome | 登录态、反爬平台、表单交互、发布操作 |
| **Crawl4AI** | 自托管 LLM-ready 爬虫 | 大批量网页采集、GEO监控 |

选择逻辑：公开数据 → bb-browser；需要登录 → web-access；批量网页 → Crawl4AI

---

## 二、小红书场景

### 方案A（推荐）：xhs_content_agent

| 属性 | 详情 |
|------|------|
| GitHub | https://github.com/hl897tech/xhs_content_agent |
| 能力 | 采集+分析+生成+发布 **全链路** |
| 技术 | Playwright 爬取，大模型分析爆款规律，自动生成文案 |
| 发布 | 支持 API / MCP 自动发布 |
| 适配度 | **极高** — 几乎就是你想做的小红书Agent |

> 这个项目跟你的需求高度重合。评估后决定是直接用它还是复用其核心逻辑。

### 方案B（备选）：MediaCrawler + 自建生成

| 属性 | 详情 |
|------|------|
| GitHub | https://github.com/NanmiCoder/MediaCrawler |
| Stars | 40K+ （同类最高） |
| 能力 | 多平台数据采集（小红书/抖音/快手/B站/微博/知乎） |
| 特点 | 只做采集，不做生成 — 适合搭配GEOFlow的M3 |
| 登录 | 二维码/Cookie，关键词+ID双模式 |
| 输出 | CSV/JSON/数据库 |

### 方案C（轻量/API级）：Spider_XHS

| 属性 | 详情 |
|------|------|
| GitHub | https://github.com/cv-cat/Spider_XHS |
| 能力 | 逆向签名算法，封装全部HTTP接口 |
| 覆盖 | PC端采集 + 创作者平台发布 + 蒲公英KOL数据 |
| 特点 | 支持"AI一键改写笔记直接上传" |

---

## 三、量化场景

### A股数据

| 工具 | 用途 | 特点 | 推荐度 |
|------|------|------|--------|
| **AKShare** | 日线/分钟线/宏观/另类数据 | 完全免费，覆盖广，爬虫本质 | ⭐⭐⭐⭐ 首选 |
| **Tushare Pro** | A股基本面/日线 | 数据质量最高，需积分(500元买断) | ⭐⭐⭐⭐ 互补 |
| **Baostock** | 历史行情 | 完全免费，无需注册 | ⭐⭐⭐ 备选 |

**推荐组合**：AKShare（主力免费数据）+ Tushare Pro（高质量基本面补充）

```python
# 安装
pip install akshare tushare
```

### 加密货币数据

| 工具 | 用途 | 特点 | 推荐度 |
|------|------|------|--------|
| **CCXT** | 100+交易所统一API | MIT协议，行业标准，Python/JS/Go | ⭐⭐⭐⭐⭐ 必选 |
| **Freqtrade** | 完整量化框架 | 基于CCXT，含回测/策略/执行 | ⭐⭐⭐⭐ 考虑 |

```python
# 安装
pip install ccxt
```

### 链上数据

| 工具 | 用途 |
|------|------|
| Dune Analytics API | SQL查询链上数据 |
| Nansen API | 智能钱包追踪 |
| The Graph | 子图查询 |

---

## 四、通用网页采集（GEO/盖洛普）

### 推荐：Crawl4AI（自托管）

| 属性 | 详情 |
|------|------|
| GitHub | https://github.com/unclecode/crawl4ai |
| Stars | 58K+ |
| 协议 | Apache 2.0，完全免费 |
| 能力 | LLM-ready 输出（Markdown/JSON），自适应爬取 |
| LLM | 支持 OpenAI/Anthropic/Ollama 本地模型 |
| 部署 | Docker 自托管，零API成本 |

### 备选：Firecrawl（API）

| 属性 | 详情 |
|------|------|
| GitHub | https://github.com/mendableai/firecrawl |
| Stars | 102K+ |
| 能力 | /scrape, /crawl, /map, /extract 四个端点 |
| 价格 | 从 $83/月起 |
| 适合 | 不想维护基础设施时 |

**Crawl4AI vs Firecrawl 选择**：
- 你要完全控制 + 免费 → Crawl4AI
- 你要快速上线 + 不管基础设施 → Firecrawl
- 你的情况：自托管能力强，选 **Crawl4AI**

---

## 五、推荐架构

```
n8n (Schedule Trigger)
  │
  │  HTTP POST 触发
  ↓
LangGraph Engine (Python)
  │
  ├── 小红书场景
  │   ├── bb-browser xiaohongshu/hot → 热榜数据
  │   ├── web-access CDP → 笔记详情（登录态）
  │   ├── LLM 分析爆款 → 生成内容
  │   └── web-access CDP → 发布草稿
  │
  ├── 量化A股
  │   ├── AKShare → 行情数据
  │   ├── 信号计算 → 交易信号
  │   ├── 风控网关 → 仓位/亏损检查
  │   └── API/人工确认 → 执行
  │
  ├── 量化Crypto
  │   ├── CCXT → 交易所数据
  │   ├── 信号计算 → 交易信号
  │   ├── 风控网关 → 流动性/滑点检查
  │   └── CCXT API → 执行
  │
  ├── GEO
  │   ├── Crawl4AI → 搜索引擎AI回答
  │   ├── LLM 分析关键词gap
  │   └── GEOFlow API → 入库发布
  │
  └── 盖洛普
      ├── Crawl4AI / bb-browser → 教练社群动态
      └── GEOFlow AI Engine → 生成报告

所有流程 → LangGraph StateGraph → PostgreSQL Checkpoint
失败自动重试 / 量化交易人工审批 / 断点续跑
```

---

## 六、实施优先级

| 顺序 | 做什么 | 工具 | 预估工时 |
|------|--------|------|---------|
| 1 | 部署 n8n（Docker） | n8n | 1h |
| 2 | 评估 xhs_content_agent | xhs_content_agent | 2h |
| 3 | 小红书采集→GEOFlow 管道 | n8n + xhs/MediaCrawler | 1-2天 |
| 4 | A股数据采集脚本 | AKShare | 半天 |
| 5 | Crypto数据采集脚本 | CCXT | 半天 |
| 6 | GEO搜索引擎监控 | Crawl4AI | 1天 |

---

## 参考链接

- [Crawl4AI vs Firecrawl 对比](https://brightdata.com/blog/ai/crawl4ai-vs-firecrawl)
- [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) — 40K+ stars 多平台爬虫
- [xhs_content_agent](https://github.com/hl897tech/xhs_content_agent) — 小红书AI全链路Agent
- [Spider_XHS](https://github.com/cv-cat/Spider_XHS) — 小红书签名逆向+发布
- [AKShare](https://github.com/akfamily/akshare) — A股免费数据接口
- [Tushare Pro](https://tushare.pro/) — A股高质量数据
- [CCXT](https://github.com/ccxt/ccxt) — 100+交易所统一API
- [n8n](https://n8n.io/) — 开源工作流自动化
- [n8n 爬虫工作流指南](https://scrapegraphai.com/blog/n8n-web-scraper)
- [2026量化数据源选型](https://zhuanlan.zhihu.com/p/2005025480454197447)
