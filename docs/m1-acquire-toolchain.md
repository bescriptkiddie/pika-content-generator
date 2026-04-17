# M1 采集模块 · 工具选型

## 总览

```
┌─────────────────────────────────────────────────────────┐
│                    M1 采集层架构                          │
│                                                          │
│  ┌─────────┐     ┌──────────────┐     ┌──────────────┐  │
│  │ 调度层   │ ──→ │ 采集执行层   │ ──→ │ 标准化输出   │  │
│  │ n8n/cron │     │ 场景采集器   │     │ AcquireResult│  │
│  └─────────┘     └──────────────┘     └──────────────┘  │
│                         │                                 │
│         ┌───────────────┼───────────────┐                │
│         ↓               ↓               ↓                │
│   小红书采集器     量化数据采集器    GEO/通用采集器      │
│   MediaCrawler     AKShare+Tushare   Crawl4AI           │
│   Spider_XHS       CCXT             Firecrawl            │
│   xhs_content_agent                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 一、工作流编排层（调度 + 串联）

### 推荐：n8n（自托管）

| 属性 | 详情 |
|------|------|
| 用途 | 定时触发采集→数据清洗→调用M2分析→传递给GEOFlow |
| 部署 | Docker 自托管，免费无限制 |
| 调度 | 内置 Schedule Trigger + Cron 表达式 |
| 集成 | HTTP Request节点可调任意API，支持Webhook |
| AI | 内置AI节点，可接OpenAI/本地模型做数据处理 |
| 优势 | 可视化编排，快速迭代，不用写调度代码 |

**为什么不用 Dify？** Dify 偏 LLM 应用编排，不擅长数据采集和定时调度。n8n 是通用工作流引擎，天然适合 ETL + 定时任务场景。

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
n8n (调度编排)
  │
  ├── 小红书场景
  │   └── xhs_content_agent 或 MediaCrawler
  │       → n8n HTTP节点调用 → 输出到 GEOFlow 队列
  │
  ├── 量化A股
  │   └── AKShare + Tushare (Python脚本)
  │       → n8n 定时触发 → 输出到量化信号管道
  │
  ├── 量化Crypto
  │   └── CCXT (Python脚本)
  │       → n8n 定时触发 → 输出到量化信号管道
  │
  ├── GEO
  │   └── Crawl4AI
  │       → n8n 定时触发 → 输出到 GEOFlow 任务
  │
  └── 盖洛普
      └── Crawl4AI (教练社群/行业动态)
          → n8n 定时触发 → 输出到盖洛普Agent

所有采集结果 → 标准化 AcquireResult → 写入 PostgreSQL → GEOFlow Worker 消费
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
