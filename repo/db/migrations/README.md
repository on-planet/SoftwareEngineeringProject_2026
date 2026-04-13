# Database Migrations

## 基本原则

- `db/init.sql` 用于全新数据库的首次初始化，包含当前最新的完整表结构。
- `db/migrations/*.sql` 用于已有数据库的增量结构变更，按文件名顺序执行。
- **API 启动时不会自动执行任何 `CREATE TABLE` 或 `ALTER TABLE` 语句**，数据库变更是部署前的独立步骤。

## 文件命名规范

迁移文件采用 `YYYYMMDD_NNN_description.sql` 的格式，例如：

```
20260324_001_incremental_snapshot_and_news_columns.sql
20260324_002_news_relation_tables.sql
20260324_003_user_workspace_and_alerts.sql
20260413_008_auth_users_is_admin.sql
```

按文件名排序即为执行顺序。

## 全新部署

对于全新的 PostgreSQL 实例，只需执行一次 `init.sql`：

```bash
psql -U <user> -d quantpulse -f repo/db/init.sql
```

在 Docker Compose 环境中，该脚本已通过 `volumes` 挂载到 PostgreSQL 容器的 `/docker-entrypoint-initdb.d/`，服务首次启动时会自动执行。

## 增量迁移

如果数据库已经存在且需要升级到新版本，请按顺序执行所有尚未应用的迁移脚本：

```bash
# Linux / macOS
for f in repo/db/migrations/*.sql; do
  echo "Applying $f"
  psql -U postgres -d quantpulse -f "$f"
done
```

```bash
# Windows PowerShell
Get-ChildItem repo\db\migrations\*.sql | ForEach-Object {
  Write-Host "Applying $($_.Name)"
  psql -U postgres -d quantpulse -f $_.FullName
}
```

## 当前已发布的迁移清单

| 文件 | 说明 |
|------|------|
| `20260324_001_incremental_snapshot_and_news_columns.sql` | 快照与新闻相关列增量 |
| `20260324_002_news_relation_tables.sql` | 新闻关系表 |
| `20260324_003_user_workspace_and_alerts.sql` | 用户工作台与告警相关表（含 `auth_users` 初始结构） |
| `20260324_004_reference_market_and_institution_data.sql` | 机构与市场参考数据表 |
| `20260325_005_user_stock_pool_items.sql` | 用户股票池条目 |
| `20260325_006_stock_strategy_autogluon.sql` | 策略与 AutoGluon 相关表 |
| `20260326_007_news_nlp_fields.sql` | 新闻 NLP 字段 |
| `20260413_008_auth_users_is_admin.sql` | 为 `auth_users` 增加 `is_admin` 管理员标识字段 |

## 注意事项

1. **执行前务必备份**，特别是生产环境。
2. 迁移脚本应尽量做到幂等（例如使用 `IF NOT EXISTS`、`IF EXISTS`），以便重复执行不会报错。
3. 如果新增表或字段涉及默认值或数据回填，应在同一份迁移脚本中一并处理。
4. 完成迁移后，建议运行 `repo/tests` 中的相关测试验证兼容性。
