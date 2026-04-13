# QuantPulse Technical Documentation

## 1. Scope

本文档描述 QuantPulse 当前已落地的技术实现，面向接手开发者、维护者和答辩汇报场景。

覆盖范围：
- 系统分层与运行链路
- API、ETL、Web 模块划分
- 数据库、缓存、配置来源
- 管理员权限模型与管理后台
- Docker 部署与 CI/CD
- 启动、回填、测试和维护要点

## 2. System Overview

QuantPulse 采用三层结构：

```text
External data sources
    -> ETL jobs / backfill scripts
    -> PostgreSQL + Redis
    -> FastAPI services
    -> Next.js frontend
```

1. **ETL 层**：负责外部数据抓取、转换、落库、缓存预热和周期调度
2. **API 层**：负责统一查询接口、用户能力接口、管理员接口和部分解释层聚合
3. **Web 层**：负责行情展示、个人空间、新闻图谱、策略分析、管理后台

## 3. Repository Layout

```text
repo/
  api/
    app/
      core/          配置、数据库、Redis 缓存、中间件、异常处理
      models/        SQLAlchemy 模型
      routers/       FastAPI 路由（自动扫描注册）
      schemas/       Pydantic schema
      services/      业务服务
      adapters/      API/ETL 解耦适配层
      tasks/         定时任务脚本
  etl/
    scheduler.py     周期调度入口
    main.py          单次任务入口
    jobs/            调度任务实现
    fetchers/        外部数据源访问封装
    loaders/         PostgreSQL / Redis 写入
    transformers/    数据转换
    utils/           环境加载、日志、数据库池等
    state/           调度状态、模型产物、回测缓存
    config/          ETL 调度配置（settings.yml）
  web/
    src/
      pages/         Next.js pages router
      components/    业务组件
      services/api/  前端 API 封装
      providers/     Auth 等全局 provider
      styles/        全局样式、CSS token、模块样式
  db/
    init.sql         全量初始化
    migrations/      增量迁移
  tests/             后端测试
```

## 4. Runtime Dependencies

### 4.1 System

- Python 3.12
- Node.js 18+
- PostgreSQL 14+
- Redis 6+
- Docker & Docker Compose（推荐部署方式）

### 4.2 Python

基础依赖：`requirements.txt`

- `fastapi`, `uvicorn`
- `sqlalchemy`, `psycopg2-binary`
- `pydantic`, `pydantic-settings`
- `redis`, `pyyaml`
- `pysnowball`, `baostock`, `akshare`, `jieba`

可选：`requirements-autogluon.txt`（AutoGluon 策略训练）

### 4.3 Frontend

- `next`, `react`, `react-dom`
- `echarts`, `echarts-for-react`
- `typescript`

## 5. Configuration Sources

### 5.1 Root `.env.local`

运行时主配置来源，API、ETL 和启动脚本都会读取。

关键字段：

- `DATABASE_URL` — PostgreSQL 连接串
- `REDIS_URL` — Redis 连接串
- `AUTH_TOKEN_SECRET` — JWT 签名密钥
- `AUTH_ADMIN_ACCOUNT` / `AUTH_ADMIN_PASSWORD` — 管理员账号密码
- `XUEQIUTOKEN` / `SNOWBALL_TOKEN` — 雪球 Cookie
- `LLM_ENABLED` / `LLM_API_KEY` / `LLM_MODEL` — LLM 增强配置

加载逻辑：
- `etl/utils/env.py` 直接从根目录读取 `.env.local`
- `api/app/core/config.py` 使用 `BaseSettings`，兼容 `.env` / `.env.local`，缺失时回退到 `etl/config/settings.yml`

### 5.2 `etl/config/settings.yml`

控制 ETL 的默认连接、连接池、时区和调度参数。Docker 部署时通过挂载 `docker/etl-settings.yml` 覆盖原配置中的 `localhost`。

## 6. Database Design

初始化脚本：`db/init.sql`
增量迁移：`db/migrations/*.sql`

核心表分类：

**市场与证券基础**
- `stocks`, `indices`, `daily_prices`, `index_constituents`

**财务、估值与风险**
- `financials`, `fundamental_score`, `stock_valuation_snapshots`, 各类指标缓存表

**新闻、事件与关系链**
- `news`, `events`, 新闻关系与传播链相关表

**用户域**
- `auth_users` — 包含 `is_admin` 管理员标识字段
- `user_watch_targets`
- `user_bought_targets`
- `user_alert_rules`
- 用户工作台相关表

**策略与模型**
- 策略运行记录、AutoGluon 模型状态、回测缓存

## 7. Authentication & Admin Model

### 7.1 Authentication

- 自研 JWT（HMAC-SHA256），Payload 包含 `sub`（user_id）、`email`、`is_admin`
- Token 通过 `/api/auth/login` 或 `/api/auth/register` 获取
- 受保护路由统一使用 `get_current_user` FastAPI 依赖做认证

### 7.2 Admin Identity

- 数据库 `auth_users.is_admin` 布尔字段持久化管理员身份
- 应用启动时（`lifespan`），`ensure_admin_user()` 自动确保环境变量中指定的管理员账号存在，且 `is_admin=True`
- JWT Token 中直接携带 `is_admin`，后端可快速鉴权

### 7.3 Admin APIs

`repo/api/app/routers/admin.py`：

- `GET /api/admin/users` — 分页用户列表
- `PATCH /api/admin/users/{user_id}` — 更新用户状态（禁用/启用、管理员权限）
- `GET /api/admin/system` — 系统状态（应用名、数据库/Redis 连接、缓存统计）
- `POST /api/admin/system/clear-cache` — 清理缓存（全部或按 pattern）
- `GET /api/admin/access/logs` — 最近访问记录（含客户端 IP）
- `GET /api/admin/access/stats` — 访问统计（Top IP、状态码分布、路径分布、每小时计数）

所有管理员 API 均通过 `require_admin` 依赖进行 `403` 鉴权。

### 7.4 Admin Frontend

页面：`/admin`

模块：
- **系统状态**：数据库/Redis 连接、内存缓存条目数、Redis 命中/未命中
- **性能监控**：平均响应时间、P95/P99、错误率(5xx)、实时 QPS、总请求数
- **访问分析**：
  - 每小时访问量趋势折线图（ECharts）
  - 状态码分布环形图（ECharts）
  - Top 10 访问 IP 表格
  - Top 10 访问路径表格
  - 最近访问记录表格（含 IP、方法、路径、状态码、耗时）
- **缓存清理**：全部清理 / 按通配符清理
- **用户管理**：用户列表、禁用/启用、设为管理员/取消管理员

数据每 10 秒自动刷新一次。

## 8. ETL Architecture

### 8.1 Components

- `etl/scheduler.py` — 周期调度入口，含锁文件控制、并行作业调度
- `etl/main.py` — 单次任务入口
- `etl/jobs/*` — 每类数据对应一个任务
- `etl/fetchers/*` — 外部数据源封装
- `etl/loaders/*` — 数据入库与缓存写入

### 8.2 Implemented Jobs

- 指数行情
- 个股详情与研究数据补全
- 财务数据与基础评分
- 新闻与事件
- 宏观序列与宏观快照
- 指数成分股
- 行业暴露
- 基金持仓
- 期货数据
- 风险/指标缓存预热

### 8.3 Scheduler Behavior

- 锁文件 `repo/state/etl.lock` 防止重复运行
- 支持按任务类型配置时间表
- 支持并行 worker
- 支持断点恢复与增量运行
- 支持保留期清理（新闻/事件 30 天，其他 7 天）
- 支持回填脚本单独触发

### 8.4 Backfill Scripts

根目录高频回填脚本：

- `start_backfill_all_stocks.cmd`
- `start_backfill_macro_news.cmd`
- `start_backfill_stock_names_sectors.cmd`

## 9. API Architecture

### 9.1 Bootstrap

入口：`api/app/main.py`

启动时完成：
- 加载项目环境变量
- 创建 FastAPI 实例
- 注册异常处理器
- 注册请求日志中间件（含 IP 记录）
- 挂载所有路由（`app/routers/__init__.py` 自动扫描）
- 调用 `ensure_admin_user()` 确保管理员账号存在

### 9.2 Router Organization

按业务域拆分：

- `auth` — 注册、登录、当前用户信息
- `admin` — 用户管理、系统状态、缓存清理、访问分析（管理员专属）
- `index` — 指数
- `stock` — 个股
- `macro` — 宏观
- `news` / `events` — 资讯和事件
- `risk` — 风险和指标
- `user_targets` / `user_workspace` / `user_alerts` — 用户域
- `strategy` — 策略与评分

### 9.3 Middleware

`RequestLogMiddleware`（`api/app/core/middleware.py`）：
- 记录每次请求的 `method`、`path`、`status`、`duration_ms`
- 记录客户端 IP（优先读取 `X-Forwarded-For`）
- 在内存中维护线程安全的环形缓冲区（最多 2000 条），供管理后台访问分析使用

### 9.4 Service Layer

承担业务逻辑：数据拼装、缓存读写、聚合接口规范化、自然语言情景映射、新闻传播链计算、组合诊断和压力测试、策略评分与回测读取。

## 10. Frontend Architecture

### 10.1 Stack

- Next.js 13 pages router
- React 18
- TypeScript
- ECharts（可视化图表）

### 10.2 Page Structure

- `/` — 首页（指数、宏观、热点概览）
- `/stocks` — 股票列表
- `/stock/[symbol]` — 个股详情
- `/stats` — 个人空间
- `/macro` — 宏观
- `/futures` — 期货
- `/insights` — 洞察
- `/strategy/smoke-butt` — 策略
- `/auth` — 登录/注册
- `/admin` — 管理后台（管理员专属）

### 10.3 Admin Page Navigation

进入 `/admin` 后，顶部导航栏隐藏所有普通页面入口（概览、股票、策略等），仅保留：
- QuantPulse 品牌
- 管理后台链接
- 返回前台链接
- 当前用户邮箱
- 登出按钮

### 10.4 Frontend Data Layer

- `services/api` — 原始 HTTP 请求封装
- `domain` — query key、normalizer
- `hooks` — 页面状态组合

### 10.5 Caching & Performance

- 请求级缓存（内存 + 持久化）
- query key 统一
- 首屏与二屏拆分加载
- 部分 SSR 预热后 prime 到共享缓存

### 10.6 Admin Visualizations

管理后台使用 `echarts-for-react` 实现：
- 每小时访问量趋势折线图（面积图）
- 状态码分布环形饼图

## 11. Docker Deployment

项目已完整容器化。

### 11.1 Images

- `repo/api/Dockerfile` — Python 3.12 slim 基础，安装依赖后运行 uvicorn
- `repo/web/Dockerfile` — Node 18 多阶段构建，生产镜像仅包含 `.next` 产物

### 11.2 Compose Services

`docker-compose.yml` 定义：

- `postgres` — PostgreSQL 15，挂载 `init.sql` 自动初始化
- `redis` — Redis 7
- `api` — FastAPI 服务
- `web` — Next.js 前端（代理到 `api:8000`）
- `etl` — 按需启动的 ETL 容器（`profile: etl`）

### 11.3 ETL in Docker

ETL 容器通过挂载 `docker/etl-settings.yml` 覆盖原 `localhost` 配置，使其连接到 Docker 内部网络的服务名 `postgres` 和 `redis`。

## 12. CI/CD

### 12.1 GitHub Actions CI

`.github/workflows/ci.yml`：
- 安装 Python 依赖并运行 `pytest`
- 前端 `npm ci` + `tsc --noEmit` + `npm run build`
- Docker Buildx 构建 API / Web 镜像（仅检查，不推送）

### 12.2 GitHub Actions CD

`.github/workflows/cd.yml`：
- Push 到 `master`/`main` 时触发
- 构建并推送镜像到 `ghcr.io`
- 通过 `appleboy/ssh-action` 登录生产服务器
- 执行 `docker compose pull` + `docker compose up -d`
- 自动清理 7 天前的旧镜像

所需 Secrets：`DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_KEY`

### 12.3 ETL Automation

`scripts/run-etl.sh` 配合服务器 `crontab` 实现定时运行：

```cron
0 2 * * * cd ~/quantpulse && bash scripts/run-etl.sh
```

脚本自动生成带时间戳的日志，并清理 30 天前的旧日志。

## 13. Testing

测试目录：`repo/tests`

覆盖领域：ETL 调度、数据源兜底、缓存策略、指数/个股服务、新闻图谱、用户域、组合压力测试、策略路由等。

常用命令：

```powershell
python -m unittest repo.tests.test_user_targets_routes -v
python -m unittest repo.tests.test_news_graph_service -v
python -m unittest repo.tests.test_portfolio_stress_service -v

cd repo\web
npx tsc --noEmit --skipLibCheck
npm run build
```

## 14. Related Documents

- 根目录快速开始：[`../README.md`](../README.md)
- Docker 部署与 CI/CD：[`../DOCKER_DEPLOY.md`](../DOCKER_DEPLOY.md)
- 仓库说明：[`README.md`](./README.md)
- 数据库迁移：[`db/migrations/README.md`](./db/migrations/README.md)
