# PikaEngine Harness 架构图

> **创建日期**: 2026-04-20
> **适用项目**: `pika-content-generator`
> **目标**: 把“多场景内容流水线”升级为“可编排、可恢复、可扩展的内容生产 Harness”。

---

## 一、先说结论

PikaEngine **已经有 Harness Engineering 的骨架**，但现在更像一个**场景驱动的 Pipeline 系统**，还不是一个完全长成的 Harness。

你现在已经有的 Harness 特征：

- 有统一状态对象 `core/langgraph/state.py`
- 有统一运行图 `core/langgraph/graph.py`
- 有多入口（CLI + API）
- 有条件分支（量化场景走 risk gate）
- 有工具封装和知识库子系统

但它还缺几层真正的 Harness 能力：

- 缺 **Control Plane**：还没有一个把场景配置编译成运行时图的层
- 缺 **Capability Contract**：很多场景逻辑仍然塞在通用节点里
- 缺 **Run Record / Event Log / Checkpoint Runtime** 的实际落地
- 缺 **统一上下文装配与执行策略**
- 缺 **真正以“任务编排”为核心的运行时**，现在更偏“按模块顺序跑”

所以更准确的判断是：

**它符合 Harness Engineering 的方向，约 65%-75% 到位。**
**它的下一步不是继续堆场景，而是把 Harness 主体补齐。**

---

## 二、你当前系统的本质

你现在的 README 里定义的是一条标准业务流水线：

```text
M1 Acquire → M2 Analyze → M3 Generate → M3.5 RiskGate → M4 Execute → M5 Feedback
```

这套东西非常适合表达业务阶段。

但 Harness Engineering 更关注的是：

```text
谁来决定这次任务跑哪条链路？
谁来拼装上下文？
谁来选择工具？
谁来决定是否需要人工审批？
谁来持久化这次运行？
谁来记录失败、重试、回放？
```

也就是说：

**M1-M5 是业务语义。**
**Harness 是运行语义。**

你现在的项目，业务语义已经很清楚，运行语义还没有完全独立出来。

---

## 三、适合 PikaEngine 的 Harness 总架构图

```text
┌──────────────────────────────────────────────────────────────┐
│                        Trigger Surface                       │
│     CLI / FastAPI / n8n Cron / Webhook / Manual Approval     │
└───────────────────────┬──────────────────────────────────────┘
                        │ run request
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                        Control Plane                         │
│ Scene Registry / Pipeline Compiler / Policy Loader           │
│ 把 scene + config 编译成可执行 run plan                       │
└───────────────────────┬──────────────────────────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                        Runtime Plane                         │
│ LangGraph Orchestrator / Checkpointer / Retry / HITL         │
│ 负责状态流转、断点恢复、人工审批、失败重试                    │
└───────────────────────┬──────────────────────────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                      Capability Plane                        │
│ M1 Acquire / M2 Analyze / M3 Generate / M3.5 Risk /          │
│ M4 Execute / M5 Feedback                                     │
│ 每一层都是标准能力接口，具体实现按 scene 插拔                 │
└───────────────────────┬──────────────────────────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                         Tool Plane                           │
│ bb-browser / web-access / Crawl4AI / AKShare / CCXT /       │
│ LLM / Prompt Engine / RAG / GEOFlow API                     │
└───────────────────────┬──────────────────────────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                          Data Plane                          │
│ Run Records / Checkpoints / Raw Artifacts / Drafts /         │
│ Knowledge Store / Execution Logs / Feedback Metrics          │
└──────────────────────────────────────────────────────────────┘
```

---

## 四、这个项目最该有的 5 层 Harness

### 1. Trigger Surface

这层是“谁发起一次 run”。

PikaEngine 不是一个聊天 Agent，它更像一个**多来源触发的生产系统**。
所以入口不该只理解成 API。

```text
可触发来源：
- CLI 手动运行
- FastAPI 调用
- n8n 定时任务
- Webhook 回调
- 人工审批后的恢复执行
```

这一层的职责不是做业务，而是统一生成一个 RunRequest。

推荐结构：

```json
{
  "run_id": "run_20260420_001",
  "scene": "xiaohongshu",
  "trigger": "cron",
  "requested_by": "system",
  "input": {...},
  "policy": {...}
}
```

---

### 2. Control Plane

这是这个项目最缺的一层。

你现在有 `scene`，也有 YAML 配置，但还没有一个真正的 **Pipeline Compiler** 去做这件事：

**把配置编译成一份运行计划。**

#### 它要做什么

```text
输入：
- scene = xiaohongshu / gallup / geo / quant
- config/scenes.yaml
- 运行策略（是否允许自动发布、是否需要人工审批）

输出：
- 这次 run 要走哪些 stage
- 每个 stage 用哪个实现
- 哪些步骤需要知识库
- 哪些步骤允许失败重试
- 哪些结果需要人工审核
```

#### 推荐输出格式

```json
{
  "scene": "gallup",
  "stages": ["acquire", "analyze", "generate", "execute", "feedback"],
  "bindings": {
    "acquire": "modules/m1-acquire/gallup",
    "analyze": "modules/m2-analyze/gallup-report",
    "generate": "modules/m3-generate/templates/gallup",
    "execute": "modules/m4-execute/gallup-deliver"
  },
  "policy": {
    "requires_human_review": false,
    "max_retries": 2,
    "store_raw_artifacts": true
  }
}
```

这层一旦有了，`graph.py` 就不再是写死的“总流程图”，而变成“运行时装配器”。

这就是 Harness 味道开始变浓的地方。

---

### 3. Runtime Plane

你现在最接近 Harness 的部分，其实就在这里。

`core/langgraph/graph.py` 已经有：

- 统一 StateGraph
- 条件分支
- human_review placeholder
- checkpointer 入口

这说明你已经有 runtime 的雏形。

但它还没完全长出来，因为现在：

- CLI / API 默认没接 checkpointer
- human review 只是 placeholder
- retry 和 run record 还没真正成为第一公民
- 中断恢复能力在文档中强，在运行时里弱

#### 这层应该承担的职责

```text
1. 运行一次 graph
2. 保存 checkpoint
3. 失败重试
4. 中途暂停
5. 等人工审批后恢复
6. 记录每个 stage 的输入 / 输出 / 错误 / 时长
```

也就是说，这层不关心“生成小红书还是 Gallup 报告”。
它只关心：

**一个 run 如何被安全地执行完。**

---

### 4. Capability Plane

这是你最该重构的层。

现在很多逻辑还是“通用节点 + scene handler map”。
这能跑，但扩展久了会越来越重。

更适合 PikaEngine 的方式是：

**M1-M5 保留为稳定接口，scene 逻辑下沉成插件实现。**

#### 推荐接口方式

```text
AcquireCapability
AnalyzeCapability
GenerateCapability
RiskCapability
ExecuteCapability
FeedbackCapability
```

每个能力层只定义 contract，不直接写业务细节。

比如：

```text
AcquireCapability.run(context) -> raw artifacts
AnalyzeCapability.run(context) -> analyzed items
GenerateCapability.run(context) -> generated assets
ExecuteCapability.run(context) -> publish/deliver results
```

#### 然后每个 scene 自己实现

```text
xiaohongshu.acquire
xiaohongshu.analyze
xiaohongshu.generate
xiaohongshu.execute

gallup.acquire
gallup.analyze
gallup.generate
gallup.execute

geo.acquire
geo.analyze
geo.generate
geo.execute
```

这样你的 graph 节点就会变薄。

节点只做三件事：

```text
1. 读取 run plan
2. 调用对应 capability
3. 写回 state
```

Harness 要薄，能力实现要清楚。

---

### 5. Data Plane

这个项目不是纯聊天产品，所以它的数据平面比一般 Agent 更重要。

推荐分成 5 类数据，而不是都堆在 `data/` 里。

```text
1. Run Records
- 每次运行的元数据
- scene / trigger / status / retries / duration

2. Checkpoints
- LangGraph 中断恢复点
- 适合 DB 存储

3. Raw Artifacts
- M1 采集到的原始数据
- 原始帖子、行情、网页片段、群聊记录

4. Generated Assets
- 草稿、报告、交易信号、待发布内容

5. Feedback & Metrics
- 发布结果、点击、转化、命中率、执行结果
```

再加一个：

```text
6. Knowledge Store
- digest
- embedding / retrieval
- profile / domain memory
```

这层拆清楚后，你后面才可能做：

- 回放某次 run
- 分析哪个 stage 最常失败
- 比较不同场景的生成效果
- 做自动优化闭环

---

## 五、PikaEngine 的真正运行闭环

这个项目最值得画的不是业务流程图，而是运行闭环图。

```text
Trigger
  ↓
Control Plane 编译 run plan
  ↓
Runtime Plane 执行 graph
  ↓
Capability Plane 完成 M1-M5
  ↓
Tool Plane 调底层工具
  ↓
Data Plane 记录产物与状态
  ↓
Feedback 回流到策略与知识库
  ↓
下一次 run 更聪明
```

这才是 PikaEngine 的 Harness 护城河。

不是“我会调 LLM”。
而是：

**我能把一个多场景生产任务稳定地跑起来，并且越跑越会调度。**

---

## 六、把你当前目录重新映射成 Harness

你现在的目录是有基础的，但语义还偏“业务模块”。

更适合的理解方式是这样：

```text
pika-content-generator/
├── api/                   # Trigger Surface 的一种入口
├── config/                # Control Plane 的输入
├── core/
│   ├── control/           # 建议新增：Scene Registry / Pipeline Compiler / Policy Loader
│   ├── runtime/           # 建议新增：Graph Runner / Checkpoint / Retry / Approval
│   ├── capabilities/      # 建议新增：M1-M5 contracts
│   ├── tools/             # 底层工具统一封装
│   ├── knowledge/         # 知识层 / RAG / digest
│   └── data/              # 建议新增：run store / artifact store / metrics store
├── modules/               # 各 scene 的具体实现
│   ├── xiaohongshu/
│   ├── gallup/
│   ├── geo/
│   └── quant/
├── scripts/               # 运维与辅助入口
└── tests/
```

### 更贴近现状的迁移版目录

如果不大改目录，可以这样演化：

```text
core/
├── langgraph/             # 保留，作为 Runtime Plane 的一部分
├── control/               # 新增
├── ai-engine/             # 真正实现，而不是 README
├── scheduler/             # 真正实现，而不是 README
├── queue/                 # 真正实现 run queue
├── knowledge/             # 已有，继续增强
└── prompt-engine/         # 作为 Tool Plane 的一部分

modules/
├── scenes/
│   ├── xiaohongshu/
│   ├── gallup/
│   ├── geo/
│   └── quant/
└── capabilities/
    ├── acquire/
    ├── analyze/
    ├── generate/
    ├── risk/
    ├── execute/
    └── feedback/
```

---

## 七、针对这个项目，最适合的架构图

这是我认为最贴合它现阶段的版本。

```text
┌────────────────────────────────────────────────────────────┐
│                       Trigger Surface                      │
│ CLI / FastAPI / n8n / Webhook / Manual Resume             │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────┐
│                       Control Plane                        │
│ Scene Registry                                             │
│ Config Loader                                              │
│ Pipeline Compiler                                          │
│ Policy Resolver                                            │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────┐
│                       Runtime Plane                        │
│ LangGraph Runner                                           │
│ Checkpointer                                               │
│ Retry / Timeout / Human Approval                           │
│ Stage Event Log                                            │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────┐
│                     Capability Plane                       │
│   Acquire → Analyze → Generate → Risk → Execute → Feedback│
│   (scene-specific implementations loaded by compiler)      │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────┐
│                        Tool Plane                          │
│ bb-browser / web-access / LLM / RAG / Prompt Engine /     │
│ AKShare / CCXT / GEOFlow API / Crawl4AI                   │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────┐
│                        Data Plane                          │
│ Run Store / Checkpoints / Raw Artifacts / Draft Store /   │
│ Knowledge Store / Publish Logs / Metrics Store            │
└────────────────────────────────────────────────────────────┘
```

---

## 八、四个业务场景，在 Harness 里怎么理解

### 小红书

它不是“小红书模块”。
它是：

```text
一个 scene
+ 一组 capability 绑定
+ 一套发布策略
+ 一套反馈指标
```

### Gallup

它不是“盖洛普分析模块”。
它是：

```text
一个高知识密度 scene
+ 强依赖知识库和案例检索
+ 偏交付型 execute
```

### GEO

它不是“写 SEO 文章”。
它是：

```text
一个搜索意图驱动 scene
+ 偏关键词 gap 分析
+ 偏站点分发 execute
```

### 量化

它不是“另一个业务功能”。
它是：

```text
一个高风险 scene
+ 必须开启 risk policy
+ 必须支持人工审批
+ 必须有强 checkpoint 与回放
```

这也是为什么你需要 Control Plane。
不同 scene，不只是模板不同，而是**运行政策不同**。

---

## 九、和 Harness Engineering 更贴近之后，你会得到什么

### 1. 不再是“场景越来越多，代码越来越乱”

因为新场景只是在注册新的 capability bindings，不是去改核心节点。

### 2. 不再是“graph 越来越硬编码”

因为 graph 只负责运行，具体跑法交给 compiler 和 policy。

### 3. 不再是“文档里有调度/审批/重试，代码里没有”

因为这些会成为 Runtime Plane 的基础设施。

### 4. 可以做真正的多场景复用

比如：

- 同一个 Analyze capability，服务多个 scene
- 同一个 Execute contract，接不同分发器
- 同一个 Feedback store，沉淀全局指标

### 5. 更像一个底座，而不是一个项目集市

这点最重要。

---

## 十、最小落地版 Harness 也可以先这样开始

如果你现在不想大改，可以先把第一步限制得很小：

```text
第一步只补三样：
1. control/pipeline_compiler.py
2. runtime/graph_runner.py
3. runtime/run_store.py
```

这样你现有代码几乎都能复用。

### 最小运行闭环

```text
API/CLI 请求
  ↓
Pipeline Compiler 生成 run plan
  ↓
Graph Runner 带 checkpoint 执行
  ↓
每个 stage 记录 run event
  ↓
结果写入 run store + artifacts store
```

只要这一步落了，整个项目的“工程重心”就会从 pipeline 变成 harness。

---

## 十一、一句话收尾

**PikaEngine 不是一个“多场景内容流水线项目”。**
**它更适合被做成一个“多场景 AI 生产 Harness”。**

M1-M5 是表层业务语言。
Control Plane + Runtime Plane + Capability Plane + Data Plane，才是它真正该长出来的身体。
