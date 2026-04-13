# QuantPulse

QuantPulse 是一个面向 A 股、港股和美股场景的多源金融数据分析平台。仓库采用单仓库（monorepo）结构，包含完整的数据采集（ETL）、REST API 服务（FastAPI）和 Web 前端（Next.js）。

## 核心能力

- **多市场行情**：指数、个股、宏观、期货、资讯聚合和事件统计
- **个人空间**：自选标的、已买标的、告警中心、新闻关系图
- **组合分析**：组合诊断报告、组合压力测试、情景实验室
- **策略模块**：可解释信号、策略评分、回测置信度
- **管理后台**：用户管理、系统状态监控、缓存清理、可视化访问分析（含 IP）
- **前端优化**：请求级缓存、首屏分层加载、ECharts 数据可视化

## 仓库结构

```
repo/
  api/      # FastAPI 后端
  etl/      # 数据采集、回填和调度
  web/      # Next.js 前端
  db/       # 数据库初始化脚本和增量迁移
  tests/    # 后端测试
docker/     # Docker 部署配置
scripts/    # 运维脚本（部署、ETL 定时）
.github/
  workflows/  # GitHub Actions CI/CD
```

## 部署方式（推荐）

项目已完整支持 **Docker Compose** 一键部署和 **GitHub Actions CI/CD** 自动发布。

详细部署文档见 [`DOCKER_DEPLOY.md`](./DOCKER_DEPLOY.md)。

### 快速启动

```bash
# 启动 PostgreSQL + Redis + API + Web
docker compose up --build -d

# 访问
# 前端 http://localhost:3000
# API  http://localhost:8000
# 文档 http://localhost:8000/docs
```

## 本地开发环境

### 环境要求

- Python `3.12`
- Node.js `18+`
- npm `9+`
- PostgreSQL `14+`
- Redis `6+`

### 安装依赖

```powershell
# Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 前端
cd repo\web
npm install
```

### 数据库初始化

```powershell
psql -U postgres -d quantpulse -f repo\db\init.sql
```

如数据库已存在旧版本结构，按 `repo/db/migrations/` 中的文件名顺序执行增量脚本。

### 配置

复制根目录 `.env.local.example` 为 `.env.local`，并修改以下关键项：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 |
| `REDIS_URL` | Redis 连接串 |
| `AUTH_TOKEN_SECRET` | JWT 签名密钥 |
| `AUTH_ADMIN_ACCOUNT` | 管理员账号，默认 `admin` |
| `AUTH_ADMIN_PASSWORD` | 管理员密码，默认 `admin` |
| `XUEQIUTOKEN` / `SNOWBALL_TOKEN` | 雪球 Cookie，用于行情抓取 |

### 本地启动

```powershell
# API
.\start_api.cmd

# 前端
.\start_web.cmd

# ETL 调度（可选）
.\start_etl.cmd
```

## 管理员账号与后台

默认管理员账号：

```
account: admin
password: admin
```

管理员登录后，导航栏会出现**管理后台**入口，进入后可执行：

- **用户管理**：查看/禁用/启用用户、分配/取消管理员权限
- **系统状态**：查看数据库/Redis 连接、内存缓存、Redis 命中统计
- **性能监控**：平均响应时间、P95/P99、错误率、实时 QPS
- **访问分析**：每小时访问量趋势图、状态码分布图、Top 10 IP/路径、最近访问记录（含 IP）
- **缓存清理**：清理全部缓存或按前缀/通配符清理

管理员身份通过数据库 `auth_users.is_admin` 字段持久化，并在 JWT Token 中携带 `is_admin` 标识。

## CI/CD

项目已配置 GitHub Actions：

- **CI**（`.github/workflows/ci.yml`）：每次 Push / PR 自动运行后端测试、前端类型检查、Docker 镜像构建
- **CD**（`.github/workflows/cd.yml`）：Push 到 `master`/`main` 时自动构建并推送镜像到 **GitHub Container Registry (ghcr.io)**，随后通过 SSH 部署到生产服务器

需要在 GitHub Secrets 中配置 `DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_KEY`。

## ETL 自动化

项目提供 `scripts/run-etl.sh`，可与服务器 `crontab` 配合实现自动数据抓取。例如每天凌晨 2 点执行：

```cron
0 2 * * * cd ~/quantpulse && bash scripts/run-etl.sh
```

手动执行一次 ETL：

```bash
docker compose --profile etl run --rm etl
```

## 数据回填脚本

根目录提供高频数据回填脚本：

- `start_backfill_all_stocks.cmd` — 股票基础信息、详情、日线、财报、事件
- `start_backfill_macro_news.cmd` — 宏观和新闻
- `start_backfill_stock_names_sectors.cmd` — 股票名称、市场和行业基础信息

## 测试

```powershell
# 后端测试示例
python -m unittest repo.tests.test_user_targets_routes -v
python -m unittest repo.tests.test_news_graph_service -v

# 前端类型检查
cd repo\web
npx tsc --noEmit --skipLibCheck

# 前端构建
npm run build
```

## 相关文档

- [`DOCKER_DEPLOY.md`](./DOCKER_DEPLOY.md) — Docker 部署与 CI/CD 完整指南
- [`repo/TECHNICAL_DOC.md`](./repo/TECHNICAL_DOC.md) — 技术架构详细说明
- [`repo/db/migrations/README.md`](./repo/db/migrations/README.md) — 数据库迁移说明
