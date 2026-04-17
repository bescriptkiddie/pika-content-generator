# Core: AI Engine

从 GEOFlow 的 `includes/ai_engine.php` 和 `includes/ai_service.php` 抽象。

## 能力

- 多模型调用（OpenAI兼容接口）
- 提示词变量替换（`{{title}}`, `{{keyword}}`, `{{Knowledge}}`）
- 条件语句（`{{#if variable}}...{{/if}}`）
- 知识库RAG注入
- 图片自动插入
- 关键词/描述自动生成
- 敏感词过滤
- 内容质量校验（最小长度）

## 来源文件

- `GEOFlow/includes/ai_engine.php` → AIEngine class
- `GEOFlow/includes/ai_service.php` → AI请求封装
- `GEOFlow/includes/knowledge-retrieval.php` → RAG检索
- `GEOFlow/includes/embedding-service.php` → Embedding服务

## 抽象方向

将 GEOFlow 的 AI 引擎从「文章生成专用」改为「通用内容生成」：
- 输入：任意结构化数据 + 提示词模板
- 输出：适配目标场景的内容
- 不绑定 articles 表，输出交给 M4 模块处理
