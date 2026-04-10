# 数据库连接池优化文档

## 问题描述

在优化前，ETL 调度器和相关任务存在以下问题：

1. **重复创建引擎**：每次调用 `_get_db_session()` 都会创建新的数据库引擎
2. **连接池浪费**：每个引擎都有独立的连接池，导致资源浪费
3. **并发冲突**：`parallel_workers=4` 但 `pool_size=5`，高并发时可能耗尽连接

## 优化方案

### 1. 创建连接池管理器

新增 `repo/etl/utils/db_pool.py` 模块，实现：

- **单例模式**：相同配置的数据库 URL 返回同一个引擎实例
- **线程安全**：使用锁保护引擎缓存
- **灵活配置**：支持自定义连接池参数

### 2. 核心函数

#### `get_engine()`
获取或创建数据库引擎（单例模式）

```python
engine = get_engine(
    database_url,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
)
```

#### `get_session_factory()`
获取或创建 Session 工厂（单例模式）

```python
factory = get_session_factory(
    database_url,
    pool_size=10,
    max_overflow=5,
)
```

#### `create_session()`
创建新的数据库 Session（使用共享连接池）

```python
session = create_session(
    database_url,
    pool_size=10,
    max_overflow=5,
)
```

#### `dispose_all_engines()`
释放所有缓存的引擎（应用关闭时调用）

```python
dispose_all_engines()
```

### 3. 修改的文件

#### `repo/etl/scheduler.py`
- 导入 `create_session` 替代直接创建引擎
- 根据 `parallel_workers` 动态调整连接池大小
- 移除 `engine.dispose()` 调用（引擎由池管理器管理）

#### `repo/etl/jobs/cache_metrics_job.py`
- 使用 `get_session_factory()` 获取共享工厂
- 根据 workers 数量动态调整连接池大小
- 移除手动 `engine.dispose()` 调用

#### `repo/etl/loaders/pg_loader.py`
- 使用 `get_engine()` 获取共享引擎
- 简化初始化逻辑

### 4. 配置建议

在 `repo/etl/config/settings.yml` 中：

```yaml
postgres:
  pool_size: 10  # 建议 >= parallel_workers + 2
  max_overflow: 5  # 建议 >= parallel_workers

etl:
  parallel_workers: 4  # 并行工作线程数
```

**计算公式**：
- `pool_size` ≥ `parallel_workers` + 2（预留给主线程和其他操作）
- `max_overflow` ≥ `parallel_workers`（应对突发并发）

### 5. 性能提升

#### 优化前
```
每次 ETL 运行：
- 创建 1 个主引擎（scheduler）
- 创建 1 个 metrics 引擎（cache_metrics_job）
- 每个 PgLoader 创建独立引擎
总计：3-5 个独立连接池
```

#### 优化后
```
整个进程生命周期：
- 共享 1 个引擎实例
- 所有 Session 使用同一个连接池
总计：1 个共享连接池
```

**资源节省**：
- 减少 60-80% 的数据库连接数
- 降低内存占用
- 提高连接复用率

### 6. 测试验证

运行测试：

```bash
python -m pytest repo/tests/test_db_pool_optimization.py -v
```

### 7. 监控建议

添加连接池监控：

```python
from etl.utils.db_pool import get_engine

engine = get_engine(database_url)
pool = engine.pool

# 监控指标
print(f"Pool size: {pool.size()}")
print(f"Checked out: {pool.checkedout()}")
print(f"Overflow: {pool.overflow()}")
print(f"Checked in: {pool.checkedin()}")
```

### 8. 注意事项

1. **不要手动 dispose 引擎**：引擎由池管理器统一管理
2. **及时关闭 Session**：使用 `try/finally` 或上下文管理器
3. **调整配置**：根据实际负载调整 `pool_size` 和 `parallel_workers`
4. **监控连接数**：定期检查数据库连接数，避免泄漏

### 9. 迁移指南

如果你的代码中有类似模式：

```python
# 旧代码
engine = create_engine(database_url, pool_pre_ping=True)
session = Session(bind=engine)
```

改为：

```python
# 新代码
from etl.utils.db_pool import create_session

session = create_session(database_url, pool_size=10, max_overflow=5)
```

## 总结

通过实现连接池单例模式，我们：
- ✅ 避免重复创建数据库引擎
- ✅ 减少数据库连接数
- ✅ 提高资源利用率
- ✅ 支持动态调整连接池大小
- ✅ 保持线程安全
