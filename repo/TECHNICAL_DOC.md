# QuantPulse Technical Documentation

## 1. Scope

本文档描述当前仓库中已经落地的 QuantPulse 技术实现，重点覆盖：

- 系统分层与运行链路
- API、ETL、Web 的模块划分
- 数据库、缓存和配置来源
- 当前已经实现的核心业务能力
- 启动、回填、测试和维护要点

面向对象：

- 需要接手本项目的开发者
- 需要做答辩、汇报或二次开发的同学
- 需要快速定位功能所在模块的维护者

## 2. System Overview

QuantPulse 采用典型的三层结构：

1. ETL 层
   - 负责外部数据抓取、转换、落库、缓存预热和周期调度
2. API 层
   - 负责统一查询接口、用户能力接口和部分解释层聚合
3. Web 层
   - 负责行情展示、个人空间、图谱、策略分析和监控面板

主数据流如下：

```text
External data sources
    -> ETL jobs / backfill scripts
    -> PostgreSQL + Redis
    -> FastAPI services
    -> Next.js frontend
```

## 3. Repository Layout

```text
repo/
  api/
    app/
      core/        # 配置、数据库、缓存、中间件、异常处理
      models/      # SQLAlchemy 模型
      routers/     # FastAPI 路由
      schemas/     # Pydantic schema
      services/    # 业务服务
      adapters/    # API/ETL 解耦适配层
  etl/
    jobs/          # 调度任务
    fetchers/      # 外部数据抓取器
    loaders/       # PostgreSQL / Redis 写入
    transformers/  # 数据转换
    utils/         # 环境加载、LLM、数据库池等工具
    state/         # 调度状态、模型产物、回测缓存
    config/        # ETL 调度配置
  web/
    src/
      pages/       # Next.js pages router
      components/  # 业务组件
      domain/      # 领域封装层
      hooks/       # 数据 hooks
      services/    # 前端 API 封装
      providers/   # Auth 等全局 provider
      styles/      # 全局样式、token、模块样式
  db/
    init.sql       # 全量初始化
    migrations/    # 增量迁移
  tests/           # 后端与服务层测试
```

## 4. Runtime Dependencies

### 4.1 System Dependencies

- Python 3.12
- Node.js 18+
- PostgreSQL 14+
- Redis 6+

### 4.2 Python Dependencies

基础依赖位于 `../requirements.txt`：

- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `psycopg2-binary`
- `pydantic`
- `pydantic-settings`
- `redis`
- `pyyaml`
- `pysnowball`
- `xlrd`
- `baostock`
- `akshare`

可选依赖：

- `requirements-autogluon.txt`
  - 用于 AutoGluon 策略训练与部分回测能力

### 4.3 Frontend Dependencies

前端依赖定义在 `web/package.json`：

- `next`
- `react`
- `react-dom`
- `echarts`
- `echarts-for-react`
- `typescript`

## 5. Configuration Sources

QuantPulse 当前有两类配置来源：

### 5.1 Root `.env.local`

根目录 `.env.local` 是运行时主配置来源，API、ETL 和启动脚本都会读取。

关键字段：

- `DATABASE_URL`
- `REDIS_URL`
- `XUEQIUTOKEN` / `SNOWBALL_TOKEN`
- `AUTH_TOKEN_SECRET`
- `AUTH_TOKEN_EXPIRE_HOURS`
- `AUTH_ADMIN_ACCOUNT`
- `AUTH_ADMIN_PASSWORD`
- `LLM_ENABLED`
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_BASE_URL`
- `SMTP_*`

环境加载逻辑：

- `etl/utils/env.py`
  - 直接从根目录读取 `.env.local`
- `api/app/core/config.py`
  - 使用 `BaseSettings`
  - 同时兼容 `.env` / `.env.local`
  - 若环境变量缺失，会回退到 `etl/config/settings.yml` 的默认数据库和 Redis 配置

### 5.2 `etl/config/settings.yml`

这个文件主要控制：

- ETL 默认 PostgreSQL / Redis 地址
- 连接池参数
- 市场时区和 T-1 偏移
- 调度并行度
- 每个 ETL 任务的执行时间

## 6. Database Design

数据库初始化脚本为 `db/init.sql`，增量迁移位于 `db/migrations`。

核心表按域分为几类：

### 6.1 市场与证券基础数据

- `stocks`
- `indices`
- `daily_prices`
- `index_constituents`

### 6.2 财务、估值与风险

- `financials`
- `fundamental_score`
- `stock_valuation_snapshots`
- 各类风险和指标缓存表

### 6.3 新闻、事件与关系链

- `news`
- `events`
- 新闻关系、主题、传播链相关表

### 6.4 用户域

- `auth_user`
- `user_watch_targets`
- `user_bought_targets`
- `user_alert_rules`
- 用户工作台相关表

### 6.5 策略与模型产物

- 策略运行记录
- AutoGluon 模型状态
- 回测缓存

## 7. ETL Architecture

### 7.1 Main Components

- `etl/scheduler.py`
  - 周期调度入口
  - 锁文件控制
  - 并行作业调度
- `etl/main.py`
  - 单次任务入口
- `etl/jobs/*`
  - 每类数据对应一类任务
- `etl/fetchers/*`
  - 外部数据源访问封装
- `etl/loaders/*`
  - 数据入库与缓存写入

### 7.2 Implemented Jobs

当前仓库已实现的重点任务包括：

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

### 7.3 Scheduler Behavior

调度器的关键行为：

- 使用锁文件防止重复运行
- 支持按任务类型配置时间表
- 支持并行 worker
- 支持部分任务断点恢复
- 支持保留期清理
- 支持回填脚本单独触发

### 7.4 Backfill Scripts

根目录提供了三个高频脚本：

- `start_backfill_all_stocks.cmd`
- `start_backfill_macro_news.cmd`
- `start_backfill_stock_names_sectors.cmd`

它们分别用于：

- 股票全链路数据回填
- 宏观和新闻回填
- 股票基础信息补全

## 8. API Architecture

### 8.1 Application Bootstrap

应用入口：`api/app/main.py`

API 启动时会完成：

- 加载项目环境变量
- 创建 FastAPI 实例
- 注册异常处理器
- 注册请求日志中间件
- 挂载所有路由

### 8.2 Router Organization

路由按业务域拆分，核心包括：

- 认证：`auth`
- 指数：`index`
- 个股：`stock`
- 宏观：`macro`
- 资讯和事件：`news` / `events`
- 风险和指标：`risk`
- 用户目标：`user_targets`
- 用户工作台和告警：`user_workspace` / `user_alerts`
- 策略与评分：`strategy`

### 8.3 Service Layer

服务层承担了大部分业务逻辑，包括：

- 数据拼装
- 缓存读写
- 聚合接口 schema 规范化
- 自然语言情景映射
- 新闻传播链与影响链计算
- 组合诊断和压力测试
- 策略评分与回测读取

### 8.4 Domain Modules

最近几轮重构后，以下能力已经收拢为相对独立的 domain/service 边界：

- 告警
- 新闻图谱
- 组合压力测试
- 组合诊断报告
- 策略评分
- Dashboard 聚合接口

目标是避免页面或路由层互相直接依赖内部实现细节。

## 9. Frontend Architecture

### 9.1 Technical Stack

- Next.js 13 pages router
- React 18
- TypeScript
- ECharts

### 9.2 Page Structure

核心页面包括：

- 首页：指数、宏观、热点概览
- `stocks`
- `stock/[symbol]`
- `stats`
- `macro`
- `futures`
- `insights`
- `strategy/smoke-butt`
- `auth`

### 9.3 Frontend Data Layer

前端数据层分为三层：

1. `services/api`
   - 原始 HTTP 请求封装
2. `domain`
   - query key、normalizer、领域级数据加载器
3. `hooks`
   - 页面状态组合和缓存使用

### 9.4 Frontend Caching Strategy

已经落地的优化包括：

- 请求级缓存
- query key 统一
- 用户维度缓存隔离
- 首屏与二屏拆分加载
- 持久化缓存
- 部分 SSR 预热后 prime 到共享缓存

### 9.5 UI and Style Architecture

样式层已经开始从“页面样式文件”过渡到：

- `styles/tokens.css`
  - 设计 token
- `styles/semantic.css`
  - 语义类
- 局部模块样式
  - 组件级模块 CSS

### 9.6 Motion and Monitoring

目前前端只保留少量有效动效：

- 首屏分组渐入
- 数字滚动
- tab 切换过渡

监控侧已经加入：

- TTFB
- FCP
- 接口耗时
- Query 缓存命中率
- 后端 `cache_hit`

性能监控面板默认隐藏，仅管理员登录后进入管理员模式可见。

## 10. Current Business Capabilities

### 10.1 News Graph Enhancement

新闻图谱已从单纯关系图升级为：

- Propagation Chains
- Impact Chains
- Drill Into News
- 个人空间关联标的 overlap

### 10.2 Explainability Layer

当前解释层已经落在：

- 告警 explanation
- 策略评分 explanation
- 情景实验室解析 explanation
- 组合画像标签 explanation

### 10.3 Scenario Lab and Portfolio Diagnostics

已实现：

- 自然语言情景输入
- 默认案例与快捷填充
- 自定义规则压力测试
- 组合诊断报告
- 观察标的诊断报告

当前策略：

- 压力测试只在“已买标的”下展示
- 观察标的下保留组合分析和诊断，不展示压力测试入口

### 10.4 Strategy and Backtest

当前策略页支持：

- 策略评分
- 信号解释
- 回测结果
- Backtest Confidence

回测侧已做：

- 磁盘缓存
- 延迟渲染
- 历史窗口收敛

## 11. Performance and Reliability

已经落实的性能/稳定性改造包括：

- API/ETL 解耦
- 数据库连接池优化
- 前端跨页面共享缓存
- 个股详情首屏/二屏拆分
- hydration mismatch 修复
- 个人空间循环渲染问题修复
- 新闻图谱去重和相关性过滤
- 右侧性能面板管理员可见性控制

专项说明见 `docs` 目录。

## 12. Testing

测试目录：`tests`

当前仓库包含 61 个测试文件，主要覆盖：

- ETL 调度和断点恢复
- 数据源兜底与兼容
- 缓存策略
- 指数和个股服务
- 新闻图谱与新闻 NLP
- 用户目标、工作台、告警
- 组合压力测试
- 策略路由与策略服务

常用命令：

```powershell
python -m unittest repo.tests.test_user_targets_routes -v
python -m unittest repo.tests.test_news_graph_service -v
python -m unittest repo.tests.test_portfolio_stress_service -v
cd web
npx tsc --noEmit --pretty false
npm run build
```

## 13. Deployment Notes

当前仓库更偏开发/课程项目结构，部署方式以本地运行和脚本驱动为主。

已具备但未完全工程化的部分：

- 环境变量管理
- 增量迁移
- ETL 锁文件
- 前端性能监控

尚未完全补齐的部分：

- 容器化部署
- CI/CD
- 标准化生产环境监控
- 更细粒度权限模型

## 14. Related Documents

- 根目录快速开始：[`../README.md`](../README.md)
- 仓库说明：[`README.md`](./README.md)
- 专项文档索引：[`docs/README.md`](./docs/README.md)
- 数据库迁移：[`db/migrations/README.md`](./db/migrations/README.md)
