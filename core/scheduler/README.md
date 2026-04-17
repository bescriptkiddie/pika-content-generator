# Core: Scheduler & Queue

从 GEOFlow 的调度系统抽象。

## 能力

- Cron 定时扫描任务
- Job Queue（pending → running → completed/failed）
- Worker claim 机制（支持多 worker 并发）
- 失败重试（可配置重试次数和间隔）
- 超时任务恢复（recoverStaleJobs）
- 心跳机制（touchHeartbeat）

## 来源文件

- `GEOFlow/bin/cron.php` → 调度器
- `GEOFlow/bin/worker.php` → Worker进程
- `GEOFlow/includes/job_queue_service.php` → 队列服务
- `GEOFlow/includes/task_service.php` → 任务管理
- `GEOFlow/includes/task_lifecycle_service.php` → 任务生命周期

## 抽象方向

- job_type 从固定的 `generate_article` 扩展为可配置
- 任务不再绑定 title_library / image_library 等 GEO 概念
- 任务配置改为 JSON payload，由各场景模块解释
- 保留 queue claim/retry/heartbeat 机制不变
