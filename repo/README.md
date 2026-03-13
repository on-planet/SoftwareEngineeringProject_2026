# KiloQuant 基础框架

该目录根据 `项目规划.md` 初始化，包含 ETL、API、前端三层骨架。

## 目录结构
- `repo/etl`: 数据采集与清洗
- `repo/api`: FastAPI 服务
- `repo/web`: 前端骨架

## 新增扩展 API
- `GET /api/events/timeline`: 事件时间线（支持 symbol/symbols/type/event_types/keyword/sort_by/start/end/limit/offset/sort）。
- `GET /api/news/aggregate`: 新闻聚合（支持 symbol/symbols/sentiment/sentiments/keyword/sort_by/start/end/limit/offset/sort）。
- `GET /api/events/stats`: 事件统计（按日/周/月 + 类型/标的，支持 symbol/symbols/type/event_types/start/end/granularity/top_date/top_type/top_symbol）。
- `GET /api/news/stats`: 新闻统计（按日/周/月 + 情绪/标的，支持 symbol/symbols/sentiment/sentiments/start/end/granularity/top_date/top_sentiment/top_symbol）。
- `GET /api/stock/{symbol}/news`: 新闻列表（支持 start/end/sentiment/sentiments/keyword/sort_by/limit/offset/sort）。
- `GET /api/stock/{symbol}/events`: 事件列表（支持 start/end/type/event_types/keyword/sort_by/limit/offset/sort）。
- `GET /api/stock/{symbol}/buyback`: 回购披露（支持 start/end/min_amount/max_amount/limit/offset/sort）。
- `GET /api/stock/{symbol}/insider`: 增减持记录（支持 start/end/type/types/min_shares/max_shares/limit/offset/sort）。
- `GET /api/stock/{symbol}/financials`: 财报列表（支持 period/min_revenue/min_net_income/limit/offset/sort）。
- `GET /api/user/{user_id}/portfolio`: 持仓列表（支持 symbol/min_shares/max_shares/limit/offset）。
- `POST /api/user/{user_id}/portfolio/batch`: 批量导入/更新持仓。
- `GET /api/user/{user_id}/portfolio/analysis`: 持仓分析（支持 top_n）。
- `GET /api/sector/exposure`: 行业暴露（支持 market/limit/offset/sort/as_of）。

## 数据库与缓存
- 数据库初始化脚本：`repo/db/init.sql`（表结构 + 索引，macro 新增 `score` 字段并在 API 输出）。
- 数据库连接配置：API 使用 `DATABASE_URL`，ETL 使用 `etl/config/settings.yml` 的 `postgres.url`。
- Redis 缓存工具：[`repo/api/app/core/cache.py`](repo/api/app/core/cache.py:1) 提供 `set_json/get_json`，默认 TTL 1 小时。
- 缓存刷新工具：[`repo/api/app/tasks/refresh_cache.py`](repo/api/app/tasks/refresh_cache.py:1) 支持 heatmap/macro/risk 写入缓存。

## ETL 骨架
- 入口：[`repo/etl/main.py`](repo/etl/main.py:1) 依次运行 index/financial/news/macro/events/index_constituent/sector_exposure job，并在调度末尾写入风险序列/指标缓存。
- Fetchers：`repo/etl/fetchers/*` 提供数据源占位调用与字段校验（新增 [`repo/etl/fetchers/news_client.py`](repo/etl/fetchers/news_client.py:1)、[`repo/etl/fetchers/index_constituent_client.py`](repo/etl/fetchers/index_constituent_client.py:1)）。
- Transformers：`repo/etl/transformers/*` 增加规范化与评分构建辅助函数（新增 [`repo/etl/transformers/sector_exposure.py`](repo/etl/transformers/sector_exposure.py:1)）。
- Loaders：[`repo/etl/loaders/pg_loader.py`](repo/etl/loaders/pg_loader.py:1) 使用 SQLAlchemy 批量 upsert。
- AI 评分摘要：ETL 在财务作业中生成评分与摘要，见[`repo/etl/jobs/financial_job.py`](repo/etl/jobs/financial_job.py:1)、[`repo/etl/utils/llm_summary.py`](repo/etl/utils/llm_summary.py:1)。
- 监控与质量：字段缺失与数值范围校验会触发告警输出（[`repo/etl/utils/normalize.py`](repo/etl/utils/normalize.py:1)、[`repo/etl/utils/alerting.py`](repo/etl/utils/alerting.py:1)）。

## AI 摘要开关（可选）
- `LLM_ENABLED=true` 启用（默认关闭，未配置将回退模板摘要）。
- `LLM_PROVIDER=openai`、`LLM_MODEL=gpt-4o-mini`、`LLM_API_KEY=...`。

## API 业务逻辑增强
- 技术指标：`/stock/{symbol}/indicators` 基于日线收盘价计算 MA/RSI，indicator 参数限制为 ma/rsi，见[`repo/api/app/services/indicator_service.py`](repo/api/app/services/indicator_service.py:1)。
- 风险快照：`/risk/{symbol}` 使用日线数据计算回撤/波动率并写入 Redis（ETL 也会按股票预写入缓存），见[`repo/api/app/services/risk_service.py`](repo/api/app/services/risk_service.py:1)。
- 风险序列：`/risk/{symbol}/series` 统一以 float 计算并返回时间序列，见[`repo/api/app/services/risk_series_service.py`](repo/api/app/services/risk_series_service.py:1)。
- 热力图缓存：读取 Redis 缓存支持 market 过滤与排序降级，若缓存缺少 market/avg_close 则回退数据库计算，见[`repo/api/app/services/heatmap_service.py`](repo/api/app/services/heatmap_service.py:1)。
- 热力图路由：`/heatmap` 在有缓存时应用排序参数并分页，见[`repo/api/app/routers/heatmap.py`](repo/api/app/routers/heatmap.py:1)。

## 前端统计面板
- 新增页面：`/stats`（见 `repo/web/src/pages/stats.tsx`），支持统计面板展示。
- 首页新增入口链接，便于跳转到统计面板。
- 统计页/个股页接入 ECharts 图表（统计/指标/风险），组件见 `repo/web/src/components/*`。

## 运维与调度
- 启动脚本：`start_api.cmd`、`start_etl.cmd`、`start_web.cmd`。
- 前端依赖安装：`install_web_deps.cmd`。
- ETL 调度入口：[`repo/etl/scheduler.py`](repo/etl/scheduler.py:1)（读取 `etl/config/settings.yml` 的 schedules）。
- 日志输出：ETL 日志写入 `logs/etl.log` 并滚动。
- 告警占位：[`repo/etl/utils/alerting.py`](repo/etl/utils/alerting.py:1)，通过 `ALERT_ENABLED=true` 启用。
- 运行前提：PostgreSQL 初始化完成（见 `repo/db/init.sql`），并配置好 `DATABASE_URL`/`REDIS_URL` 或 `etl/config/settings.yml`。

## 下一步
- 补充依赖与启动脚本
- 实现 ETL 具体采集逻辑
- 完成 API 业务查询逻辑
- 接入前端页面
