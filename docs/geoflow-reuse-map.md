# GEOFlow 复用清单

## 直接复用（core 层）

| GEOFlow 文件 | PikaEngine 用途 | 改动量 |
|-------------|----------------|--------|
| `includes/ai_engine.php` | core/ai-engine | 中：解耦 articles 表绑定 |
| `includes/ai_service.php` | core/ai-engine | 小：通用AI请求封装 |
| `includes/knowledge-retrieval.php` | core/knowledge | 小：直接复用 |
| `includes/embedding-service.php` | core/knowledge | 小：直接复用 |
| `includes/job_queue_service.php` | core/queue | 小：job_type 可配置化 |
| `includes/task_service.php` | core/scheduler | 中：任务配置改为JSON |
| `includes/task_lifecycle_service.php` | core/scheduler | 小：生命周期逻辑通用 |
| `bin/cron.php` | core/scheduler | 小：调度逻辑通用 |
| `bin/worker.php` | core/scheduler | 中：按 job_type 分发到不同模块 |

## 场景复用（GEO 模块直接用）

| GEOFlow 文件 | PikaEngine 用途 |
|-------------|----------------|
| `includes/article_service.php` | modules/m4-execute/geo-site |
| `includes/seo_functions.php` | modules/m4-execute/geo-site |
| `includes/catalog_service.php` | modules/m4-execute/geo-site |
| `admin/*` | GEO场景后台（原样保留） |
| `index.php` / `article.php` | GEO前台（原样保留） |

## 不复用（需新建）

| 能力 | 说明 |
|------|------|
| 数据采集 | GEOFlow 无此能力，M1 全部新建 |
| 效果反馈 | GEOFlow 只有执行日志，M5 全部新建 |
| 小红书发布 | 新增 M4 适配器 |
| 交易执行 | 新增 M4 适配器 |
| 风控网关 | 新增 M3.5 模块 |
