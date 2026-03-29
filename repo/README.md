# QuantPulse Repository Guide

这个目录是 QuantPulse 的核心代码仓库，真正的运行代码都在这里：

- [`api`](./api)：FastAPI 后端
- [`etl`](./etl)：采集、回填、调度和缓存预热
- [`web`](./web)：Next.js 前端
- [`db`](./db)：数据库初始化与迁移脚本
- [`tests`](./tests)：后端测试
- [`docs`](./docs)：专项优化与设计说明

## 1. 推荐阅读顺序

如果你第一次接触这个项目，按下面顺序看文档最省时间：

1. 根目录快速开始：[`../README.md`](../README.md)
2. 技术架构说明：[`TECHNICAL_DOC.md`](./TECHNICAL_DOC.md)
3. 专项设计文档索引：[`docs/README.md`](./docs/README.md)
4. 数据库迁移说明：[`db/migrations/README.md`](./db/migrations/README.md)

## 2. 子目录职责

### `api`

- 路由：`api/app/routers`
- 业务服务：`api/app/services`
- 数据模型：`api/app/models`
- 响应 schema：`api/app/schemas`
- 配置与中间件：`api/app/core`

### `etl`

- 调度入口：`etl/scheduler.py`
- 单次任务入口：`etl/main.py`
- 任务实现：`etl/jobs`
- 数据抓取器：`etl/fetchers`
- 数据加载器：`etl/loaders`
- 调度状态和模型产物：`etl/state`

### `web`

- 页面：`web/src/pages`
- 组件：`web/src/components`
- API 封装：`web/src/services`
- domain 层：`web/src/domain`
- hooks：`web/src/hooks`
- 样式：`web/src/styles`

### `db`

- 全量初始化：`db/init.sql`
- 增量迁移：`db/migrations/*.sql`

### `tests`

- 当前为后端与服务层测试
- 运行方式示例见 [`../README.md`](../README.md)

## 3. 当前重点能力

当前仓库已实现并仍在维护的核心能力包括：

- 多市场行情、指数和个股详情
- 宏观快照、序列和事件/新闻统计
- 自选标的、已买标的、个人空间
- 告警中心、新闻传播链与影响链
- 组合诊断报告、组合压力测试、情景实验室
- 策略评分、回测置信度、解释层
- 前端缓存策略、懒加载、性能监控

## 4. 说明

- 启动脚本、`.env.local` 和虚拟环境位于工作区根目录，不在 `repo` 目录内。
- 如果你只是要运行项目，请直接看 [`../README.md`](../README.md)。
- 如果你要理解实现细节，再看 [`TECHNICAL_DOC.md`](./TECHNICAL_DOC.md)。
