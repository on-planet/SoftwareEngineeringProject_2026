# QuantPulse Repository Guide

这个目录是 QuantPulse 的核心代码仓库，包含全部运行代码。

## 子目录职责

```
repo/
  api/          FastAPI 后端服务
  etl/          数据采集、回填、调度与缓存预热
  web/          Next.js 前端应用
  db/           数据库初始化与增量迁移脚本
  tests/        后端与服务层测试
  docs/         专项优化与设计说明（历史文档）
```

### `api`

- 路由：`app/routers` — 包含认证、指数、个股、宏观、资讯、用户、策略、**管理员**
- 业务服务：`app/services`
- 数据模型：`app/models` — SQLAlchemy ORM 定义
- 响应 Schema：`app/schemas` — Pydantic 模型
- 配置与中间件：`app/core` — 配置加载、DB 连接、Redis 缓存、请求日志（含 IP 记录）、异常处理

### `etl`

- 调度入口：`scheduler.py` — 带锁文件的周期调度器，支持并行 worker
- 单次任务入口：`main.py`
- 任务实现：`jobs/` — 指数、财务、新闻、宏观、期货、行业暴露等
- 数据抓取器：`fetchers/` — AkShare、Baostock、pysnowball 等封装
- 数据加载器：`loaders/` — PostgreSQL / Redis 写入
- 调度状态：`state/` — 锁文件、ETL 运行状态

### `web`

- 页面：`src/pages` — 概览、股票、个股详情、宏观、期货、洞察、策略、个人空间、**管理后台**
- 组件：`src/components`
- API 封装：`src/services/api`
- 全局状态：`src/providers` — Auth 认证上下文
- 样式：`src/styles` — CSS 变量、语义类、模块样式

### `db`

- 全量初始化：`init.sql`
- 增量迁移：`migrations/*.sql`，按文件名顺序执行

## 当前重点能力

- **行情与宏观**：多市场指数、个股详情、宏观快照、期货数据
- **资讯与图谱**：新闻聚合、事件统计、新闻关系链与传播链
- **用户域**：自选/已买标的、告警中心、个人空间、组合诊断、压力测试
- **策略**：策略评分、回测结果、信号解释
- **管理后台**：基于 `is_admin` 的用户管理、系统监控、访问分析可视化、缓存运维
- **工程化**：Docker Compose 部署、GitHub Actions CI/CD、ETL 自动化脚本

## 推荐阅读顺序

1. 根目录快速开始：[`../README.md`](../README.md)
2. Docker 部署指南：[`../DOCKER_DEPLOY.md`](../DOCKER_DEPLOY.md)
3. 技术架构说明：[`TECHNICAL_DOC.md`](./TECHNICAL_DOC.md)
4. 数据库迁移说明：[`db/migrations/README.md`](./db/migrations/README.md)
