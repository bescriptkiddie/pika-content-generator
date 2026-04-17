# PikaEngine — 多场景 AI 内容引擎

> 基于 GEOFlow 底座，构建跨场景的 AI 内容生产与执行系统。

## 架构概览

```
┌───────────────────────────────────────────────────────┐
│                    PikaEngine                          │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ M1:采集  │→│ M2:分析  │→│ M3:生成  │            │
│  │ Acquire  │  │ Analyze  │  │ Generate │            │
│  └──────────┘  └──────────┘  └──────────┘            │
│                                    ↓                   │
│               ┌──────────┐  ┌──────────┐  ┌────────┐ │
│               │ M5:反馈  │←│ M4:执行  │←│M3.5:风控│ │
│               │ Feedback │  │ Execute  │  │RiskGate│ │
│               └──────────┘  └──────────┘  └────────┘ │
└───────────────────────────────────────────────────────┘
```

## 四个业务场景

| 场景 | M1 数据源 | M3 输出 | M4 执行 |
|------|----------|---------|---------|
| **小红书** | 热点/竞品笔记 | 小红书图文 | 发布到小红书 |
| **盖洛普Agent** | 教练社群/行业动态 | 分析报告/对话 | 交付给教练 |
| **GEO** | 搜索引擎AI回答 | SEO/GEO文章 | 发布到站点(GEOFlow) |
| **量化(A股+B圈)** | 行情/链上/舆情 | 交易信号 | 下单/调仓 |

## 核心层（来自 GEOFlow）

- **AI Engine** — 多模型调用、提示词变量、知识库RAG
- **Scheduler** — Cron + Worker 调度
- **Queue** — Job claim/complete/fail/retry
- **Knowledge** — Embedding 检索
- **Prompt Engine** — 模板变量系统

## 项目结构

```
PikaEngine/
├── core/                      # 核心层（从GEOFlow抽象）
│   ├── ai-engine/             # AI调用引擎
│   ├── scheduler/             # 任务调度器
│   ├── queue/                 # 队列服务
│   ├── knowledge/             # 知识库 & RAG
│   └── prompt-engine/         # 提示词模板系统
│
├── modules/                   # 业务模块层
│   ├── m1-acquire/            # M1: 数据采集
│   │   ├── xiaohongshu/       # 小红书热点采集
│   │   ├── quant-a-stock/     # A股行情数据
│   │   ├── quant-crypto/      # 加密货币数据
│   │   ├── gallup/            # 盖洛普社群数据
│   │   └── geo/               # 搜索引擎GEO数据
│   │
│   ├── m2-analyze/            # M2: 数据分析
│   │   ├── trending/          # 热点匹配度打分
│   │   ├── signal/            # 量化信号计算
│   │   ├── gallup-report/     # Gallup报告解读
│   │   └── keyword-gap/       # GEO关键词gap分析
│   │
│   ├── m3-generate/           # M3: 内容生成
│   │   ├── templates/         # 各场景提示词模板
│   │   └── adapters/          # 输出格式适配器
│   │
│   ├── m3-5-risk-gate/        # M3.5: 风控网关（量化专用）
│   │
│   ├── m4-execute/            # M4: 执行/分发
│   │   ├── xiaohongshu/       # 小红书发布
│   │   ├── geo-site/          # GEO站点发布（GEOFlow原生）
│   │   ├── gallup-deliver/    # 盖洛普报告交付
│   │   └── trading/           # 交易执行
│   │
│   └── m5-feedback/           # M5: 效果反馈
│       ├── metrics/           # 指标定义
│       └── collectors/        # 数据收集器
│
├── config/                    # 配置文件
├── docs/                      # 文档
├── scripts/                   # 运维脚本
└── tests/                     # 测试
```

## 实施路径

| Phase | 目标 | 状态 |
|-------|------|------|
| P1 | 小红书：M1采集 + M3生成 + M4发布 | 进行中 |
| P1.5 | 量化：M1数据 + M2信号 + M3.5风控 | 同步推进 |
| P2 | 盖洛普Agent：复用M1/M3 + Gallup解析 | 每周固定 |
| P3 | GEO：复用M1/M3 + GEO分发 | 观察仓位 |

## 底座依赖

- [GEOFlow](https://github.com/yaojingang/GEOFlow) — PHP, PostgreSQL, Docker
- GEOFlow 提供：AI引擎、任务调度、队列、内容工作流、SEO发布

## 设计原则

1. **配置驱动** — M1的数据源、M3的输出模板、M4的发布目标都是配置项
2. **模块独立** — 每个模块可独立开发、测试、部署
3. **场景无关** — 核心层不绑定任何业务场景
4. **风控前置** — 涉及资金的M4必须经过M3.5风控网关
