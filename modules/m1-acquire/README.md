# M1: 数据采集模块

## 职责

从外部数据源获取结构化数据，输出标准化的数据包供 M2 分析。

## 统一接口

每个采集器实现相同的接口：

```
interface Acquirer {
    // 执行一次采集，返回结构化数据列表
    acquire(config: AcquireConfig): AcquireResult[]

    // 检查数据源是否可用
    healthCheck(): boolean
}

AcquireResult {
    source: string          // 数据源标识
    type: string            // 数据类型（topic/price/article/signal）
    timestamp: datetime     // 采集时间
    raw_data: object        // 原始数据
    metadata: object        // 附加信息（来源URL、作者等）
}
```

## 子模块

### xiaohongshu/
- 热门话题采集
- 竞品笔记监控
- 关键词搜索结果

### quant-a-stock/
- 行情数据（日线/分钟线）
- 公告/研报
- 资金流向

### quant-crypto/
- CEX 行情（通过 CCXT）
- 链上数据（Dune/Nansen API）
- 社媒舆情

### gallup/
- 教练社群动态
- 行业趋势文章

### geo/
- 搜索引擎 AI 回答监控
- 品牌关键词排名
- 竞品 GEO 内容

## 技术选型

待调研：
- [ ] 通用爬虫框架（Crawl4AI / Firecrawl / 自建）
- [ ] 工作流引擎（n8n / Dify / 自建）
- [ ] 金融数据API（tushare / akshare / CCXT）
- [ ] 小红书专用工具
