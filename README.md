# QuantPulse

QuantPulse 是一个面向 A 股、港股和美股场景的多源金融数据分析平台，当前仓库同时包含：

- `repo/api`：FastAPI 后端
- `repo/etl`：数据采集、回填和调度
- `repo/web`：Next.js 前端
- `repo/db`：数据库初始化脚本和增量迁移
- 根目录启动脚本：`start_api.cmd`、`start_etl.cmd`、`start_web.cmd`

项目当前已经落地的主要能力包括：

- 指数、个股、宏观、期货、资讯聚合和事件统计
- 个人空间、自选/已买标的、告警中心、新闻关系图
- 组合诊断报告、组合压力测试、情景实验室
- 可解释信号、策略评分、回测置信度
- 前端请求缓存、首屏分层加载、性能监控面板

详细架构说明见 [repo/TECHNICAL_DOC.md](./repo/TECHNICAL_DOC.md)。

## 1. 环境要求

推荐环境：

- Python `3.12`
- Node.js `18+`
- npm `9+`
- PostgreSQL `14+`
- Redis `6+`

Windows 下建议在仓库根目录创建 `.venv`，这样根目录的 `start_api.cmd` 会优先使用它。

## 2. 依赖说明

### 2.1 后端和 ETL 依赖

安装文件：[`requirements.txt`](./requirements.txt)

主要依赖：

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

安装命令：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2.2 前端依赖

安装文件：[`repo/web/package.json`](./repo/web/package.json)

主要依赖：

- `next`
- `react`
- `react-dom`
- `echarts`
- `echarts-for-react`
- `typescript`

安装命令：

```powershell
cd repo\web
npm install
cd ..\..
```

也可以直接执行：

```powershell
.\install_web_deps.cmd
```

### 2.3 可选依赖

如果要重新训练或运行 AutoGluon 相关策略能力，额外安装：

```powershell
python -m pip install -r repo\requirements-autogluon.txt --target repo\.vendor\autogluon
```

## 3. 基础服务准备

### 3.1 PostgreSQL

1. 创建数据库，推荐库名：`quantpulse`
2. 初始化表结构：

```powershell
psql -U postgres -d quantpulse -f repo\db\init.sql
```

如果数据库已存在旧版本结构，再按 [`repo/db/migrations`](./repo/db/migrations) 中的顺序执行增量脚本。

### 3.2 Redis

默认地址：

```text
redis://localhost:6379/0
```

用于 API 缓存、ETL 缓存和部分实时查询结果。

## 4. 配置方式

### 4.1 `.env.local`

根目录的 `.env.local` 会被 API、ETL 和部分脚本共同读取。建议从模板复制：

```powershell
Copy-Item .env.local.example .env.local
```

关键配置项如下：

| 变量 | 是否必需 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 是 | PostgreSQL 连接串 |
| `REDIS_URL` | 是 | Redis 连接串 |
| `XUEQIUTOKEN` | 建议 | 雪球 Cookie，用于行情/资讯抓取 |
| `SNOWBALL_TOKEN` | 可选 | `XUEQIUTOKEN` 的别名 |
| `AUTH_TOKEN_SECRET` | 是 | 登录态签名密钥 |
| `AUTH_TOKEN_EXPIRE_HOURS` | 否 | Token 过期时间，默认 24 小时 |
| `AUTH_ADMIN_ACCOUNT` | 否 | 管理员账号，默认 `admin` |
| `AUTH_ADMIN_PASSWORD` | 否 | 管理员密码，默认 `admin` |
| `LLM_ENABLED` | 否 | 是否启用 LLM 摘要/解释增强 |
| `LLM_PROVIDER` | 否 | 当前默认 `openai` |
| `LLM_API_KEY` | 否 | 启用 LLM 时必填 |
| `LLM_MODEL` | 否 | 默认 `gpt-4o-mini` |
| `LLM_BASE_URL` | 否 | 自定义模型网关地址 |
| `SMTP_*` | 否 | 邮件验证码/通知预留配置 |

说明：

- `.env.local` 不应提交到仓库。
- 当前仓库已有一份本地文件，里面是开发机配置；对外使用时请改成你自己的连接串和密钥。
- 管理员模式的前端性能面板只有管理员账号登录后才能进入。

### 4.2 `repo/etl/config/settings.yml`

这个文件控制 ETL 的默认数据库连接、Redis 地址和调度参数，主要字段：

- `postgres.url`
- `postgres.pool_size`
- `postgres.max_overflow`
- `redis.url`
- `market.timezone`
- `market.t1_offset_days`
- `etl.parallel_workers`
- `etl.schedules.*`

如果 `.env.local` 和 `settings.yml` 同时配置了数据库/Redis，运行时以环境变量为准。

## 5. 启动方式

### 5.1 推荐方式：分别启动三个服务

### 启动 API

Windows 脚本：

```powershell
.\start_api.cmd
```

手动启动：

```powershell
cd repo\api
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 启动 ETL 调度

Windows 脚本：

```powershell
.\start_etl.cmd
```

说明：

- 这个脚本会在后台启动 `etl.scheduler`
- 这个脚本当前默认绑定了开发机的 Python 路径
- 如果你的 Python 安装位置不同，优先直接使用下面的手动命令，或者按需修改脚本

手动启动：

```powershell
$env:PYTHONPATH="$PWD\repo;$PWD\repo\api"
python -m etl.scheduler
```

停止 ETL：

```powershell
.\stop_etl.cmd
```

### 启动前端

Windows 脚本：

```powershell
.\start_web.cmd
```

手动启动：

```powershell
cd repo\web
npm run dev
```

### 5.2 服务地址

- 前端：`http://localhost:3000`
- API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`

## 6. 首次运行建议流程

建议第一次按下面顺序执行：

1. 安装 Python 依赖
2. 安装前端依赖
3. 启动 PostgreSQL 和 Redis
4. 创建并初始化 `quantpulse` 数据库
5. 配置 `.env.local`
6. 启动 API
7. 启动 ETL
8. 启动前端
9. 登录前端检查数据是否可读
10. 如果数据库是空库，再执行一次数据回填

## 7. 数据回填脚本

根目录提供了几个常用回填脚本：

- `start_backfill_all_stocks.cmd`
  - 回填股票基础信息、详情快照、研究、日线、财报和事件
- `start_backfill_macro_news.cmd`
  - 回填宏观和新闻
- `start_backfill_stock_names_sectors.cmd`
  - 补齐股票名称、市场和行业基础信息

常见用法：

```powershell
.\start_backfill_all_stocks.cmd --dry-run
.\start_backfill_macro_news.cmd --include-worldbank
.\start_backfill_stock_names_sectors.cmd --symbols 000001.SZ,0700.HK
```

## 8. 账号与权限

默认管理员账号：

```text
account: admin
password: admin
```

用途：

- 登录后台管理能力
- 打开前端管理员模式
- 查看右侧性能监控面板

如果不想用默认值，可以在 `.env.local` 里改：

```dotenv
AUTH_ADMIN_ACCOUNT=admin
AUTH_ADMIN_PASSWORD=change_me
```

## 9. 测试、构建与校验

### 9.1 后端测试

```powershell
python -m unittest repo.tests.test_user_targets_routes -v
python -m unittest repo.tests.test_news_graph_service -v
python -m unittest repo.tests.test_portfolio_stress_service -v
```

### 9.2 前端类型检查

```powershell
cd repo\web
npx tsc --noEmit --pretty false
```

### 9.3 前端构建

```powershell
cd repo\web
npm run build
```

## 10. 常见问题

### 10.1 API 启动时报缺少模块

先确认激活了虚拟环境，并已执行：

```powershell
pip install -r requirements.txt
```

### 10.2 ETL 启动失败或重复运行

- 检查 `repo/state/etl.lock`
- 先执行 `.\stop_etl.cmd`
- 再重新执行 `.\start_etl.cmd`

### 10.3 前端无法获取数据

优先检查：

- API 是否已经启动在 `8000`
- `.env.local` 的数据库和 Redis 是否可连接
- 数据库是否已初始化
- 是否已经执行过基础回填

### 10.4 雪球相关抓取失败

通常是 `XUEQIUTOKEN` 失效。更新 `.env.local` 中的 Cookie 后重启 API 和 ETL。

### 10.5 前端构建报 `.next/trace` 或 `EPERM`

一般是本地文件锁或 dev server 占用，先关闭已有 Next.js 进程，再删除 `repo/web/.next` 后重新构建。

## 11. 相关文档

- 快速使用与部署：[`README.md`](./README.md)
- 技术架构：[`repo/TECHNICAL_DOC.md`](./repo/TECHNICAL_DOC.md)
- 仓库子目录说明：[`repo/README.md`](./repo/README.md)
- 专项优化文档索引：[`repo/docs/README.md`](./repo/docs/README.md)
- 数据库迁移说明：[`repo/db/migrations/README.md`](./repo/db/migrations/README.md)
