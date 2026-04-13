# Docker 部署与 CI/CD 指南

## 目录结构说明

- `repo/api` — FastAPI 后端
- `repo/web` — Next.js 前端
- `repo/etl` — Python ETL 数据 pipeline
- `repo/db` — 数据库初始化与迁移脚本
- `.github/workflows` — GitHub Actions CI/CD
- `scripts/` — 部署与运维脚本

## 核心服务

`docker-compose.yml` 包含以下服务：

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| postgres | postgres:15-alpine | 5432 | PostgreSQL 数据库 |
| redis | redis:7-alpine | 6379 | Redis 缓存 |
| api | 本地构建 / ghcr.io | 8000 | FastAPI 接口服务 |
| web | 本地构建 / ghcr.io | 3000 | Next.js 前端服务 |
| etl | 本地构建（按需） | — | ETL 数据抓取任务 |

## 快速启动（本地/开发）

### 1. 确保已安装 Docker 和 Docker Compose

```bash
docker --version
docker compose version
```

### 2. 构建并启动核心服务

在项目根目录执行：

```bash
docker compose up --build -d
```

首次启动会自动：
- 拉取 `postgres:15-alpine` 和 `redis:7-alpine` 镜像
- 构建 `api` 和 `web` 镜像
- 初始化 PostgreSQL 数据库（执行 `repo/db/init.sql`）

### 3. 访问应用

- 前端地址：http://localhost:3000
- API 地址：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 4. 运行 ETL（可选）

ETL 默认不随核心服务一起启动，需要显式指定 profile：

```bash
docker compose --profile etl run --rm etl
```

## CI/CD 自动部署（GitHub Actions）

### 流程概览

1. **CI**：每次 Push / Pull Request 自动运行后端测试、前端构建、Docker 镜像构建检查
2. **CD**：Push 到 `master` 或 `main` 分支时：
   - 构建 API / Web Docker 镜像
   - 推送到 **GitHub Container Registry (ghcr.io)**
   - SSH 登录生产服务器，拉取最新镜像并重启服务

### 需要配置的 GitHub Secrets

在仓库 **Settings → Secrets and variables → Actions → Repository secrets** 中添加：

| Secret 名称 | 说明 |
|-------------|------|
| `DEPLOY_HOST` | 生产服务器 IP 或域名 |
| `DEPLOY_USER` | SSH 登录用户名（如 `root` 或 `ubuntu`） |
| `DEPLOY_KEY` | SSH 私钥（`~/.ssh/id_rsa` 的完整内容） |

> **注意**：`GITHUB_TOKEN` 由 GitHub 自动提供，无需手动创建。

### 服务器准备工作

1. **安装 Docker 和 Docker Compose**
2. **将当前用户加入 docker 组**（可选，避免每次用 `sudo`）：
   ```bash
   sudo usermod -aG docker $USER
   ```
3. **在项目目录放置代码**：
   ```bash
   git clone https://github.com/on-planet/2026SoftwareEngineeringProject.git ~/quantpulse
   cd ~/quantpulse
   ```
4. **确保服务器防火墙开放**：3000（前端）、8000（API，如需要直接访问）

### ETL 自动化定时运行

项目提供了 `scripts/run-etl.sh`，可与系统 `crontab` 配合实现每天自动抓取数据。

#### 配置方法

编辑当前用户的 crontab：

```bash
crontab -e
```

添加以下内容（示例：每天凌晨 02:00 执行 ETL）：

```cron
# QuantPulse ETL 定时任务
0 2 * * * cd ~/quantpulse && bash scripts/run-etl.sh >> /dev/null 2>&1
```

如果需要保留日志：

```cron
0 2 * * * cd ~/quantpulse && bash scripts/run-etl.sh >> ~/quantpulse/logs/etl-cron-combined.log 2>&1
```

#### 验证 cron 是否生效

```bash
crontab -l
```

## 环境变量

`docker-compose.yml` 支持通过环境变量或 `.env` 文件自定义配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_PASSWORD` | `123456` | PostgreSQL 密码 |
| `AUTH_TOKEN_SECRET` | `CHANGE_ME_TO_A_RANDOM_SECRET` | JWT 签名密钥 |
| `AUTH_ADMIN_ACCOUNT` | `admin` | 管理员账号 |
| `AUTH_ADMIN_PASSWORD` | `admin` | 管理员密码 |
| `API_IMAGE` | `quantpulse-api:latest` | API 镜像名称 |
| `WEB_IMAGE` | `quantpulse-web:latest` | Web 镜像名称 |

示例（Linux/macOS）：

```bash
POSTGRES_PASSWORD=yourpassword AUTH_TOKEN_SECRET=yoursecret docker compose up -d
```

Windows PowerShell：

```powershell
$env:POSTGRES_PASSWORD="yourpassword"; $env:AUTH_TOKEN_SECRET="yoursecret"; docker compose up -d
```

## 常用命令

```bash
# 查看日志
docker compose logs -f api
docker compose logs -f web

# 重启服务
docker compose restart api

# 停止所有服务
docker compose down

# 停止并删除数据卷（⚠️ 会清空数据库）
docker compose down -v

# 进入 API 容器
docker compose exec api bash

# 进入 PostgreSQL
docker compose exec postgres psql -U postgres -d quantpulse

# 手动运行 ETL
docker compose --profile etl run --rm etl

# 手动执行部署脚本（服务器上）
bash scripts/deploy.sh
```

## 数据库迁移

如果是**全新部署**，`repo/db/init.sql` 已经包含最新的表结构，无需额外执行迁移。

如果是**已有数据迁移到 Docker**，请根据 `repo/db/migrations/` 下的脚本按顺序执行 `ALTER TABLE` 等增量变更。

## 网络说明

- 前端 (`web`) 通过 `API_PROXY_TARGET=http://api:8000` 代理到后端。
- 后端 (`api`) 通过 `DATABASE_URL` 和 `REDIS_URL` 环境变量连接 `postgres` 和 `redis`。
- ETL 通过挂载 `docker/etl-settings.yml` 覆盖原配置中的 `localhost` 为 Docker 内部服务名。
