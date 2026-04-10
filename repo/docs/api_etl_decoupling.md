# API 与 ETL 层解耦方案

## 问题分析

### 原有架构问题

在优化前，API 层直接依赖 ETL 层：

```
┌─────────────────────────┐
│   API 层                │
│  (live_market_service)  │
└───────────┬─────────────┘
            │ 直接导入
            ↓
┌─────────────────────────┐
│   ETL 层                │
│  (fetchers/transformers)│
└─────────────────────────┘
```

**具体问题：**

1. **紧耦合**：`live_market_remote.py` 直接导入 ETL 的 fetchers
   ```python
   from etl.fetchers.snowball_client import get_stock_quote
   from etl.fetchers.market_client import get_stock_basic
   ```

2. **难以测试**：API 测试必须依赖真实的 ETL 实现
3. **难以替换**：无法轻易切换到其他数据源
4. **部署耦合**：API 和 ETL 必须部署在一起

## 解决方案

### 新架构设计

引入数据适配层（Data Access Layer）：

```
┌─────────────────────────┐
│   API 层                │
│  (live_market_service)  │
└───────────┬─────────────┘
            │ 调用接口
            ↓
┌─────────────────────────┐
│   数据适配层             │
│  (adapters)             │
│  ┌───────────────────┐  │
│  │ MarketDataAdapter │  │
│  └─────────┬─────────┘  │
│            │             │
│  ┌─────────┴─────────┐  │
│  │   Provider 接口   │  │
│  └─────────┬─────────┘  │
└────────────┼─────────────┘
             │
    ┌────────┴────────┐
    │                 │
┌───┴────┐      ┌────┴────┐
│  ETL   │      │  Mock   │
│Provider│      │Provider │
└────────┘      └─────────┘
```

### 核心组件

#### 1. MarketDataProvider 协议 (`market_data_adapter.py`)

定义统一的数据访问接口：

```python
class MarketDataProvider(Protocol):
    def get_stock_basic(...) -> list[dict]: ...
    def get_stock_quote(...) -> dict | None: ...
    def get_stock_quote_detail(...) -> dict | None: ...
    # ... 其他方法
```

#### 2. EtlMarketDataProvider (`etl_market_provider.py`)

基于 ETL 层的实现：

```python
class EtlMarketDataProvider:
    def get_stock_basic(self, symbols, ...):
        # 调用 ETL 层的 fetchers
        return _get_stock_basic(symbols, ...)
```

#### 3. MockMarketDataProvider (`mock_market_provider.py`)

用于测试的 Mock 实现：

```python
class MockMarketDataProvider:
    def get_stock_basic(self, symbols, ...):
        # 返回预定义的测试数据
        return self._test_data.get("stock_basic", [])
```

#### 4. MarketDataAdapter (`market_data_adapter.py`)

适配器类，封装提供者：

```python
class MarketDataAdapter:
    def __init__(self, provider: MarketDataProvider):
        self._provider = provider
    
    def get_stock_basic(self, ...):
        return self._provider.get_stock_basic(...)
```

#### 5. 工厂函数 (`factory.py`)

提供全局单例：

```python
def get_market_data_adapter() -> MarketDataAdapter:
    # 返回单例适配器
    return _adapter_instance

def set_market_data_adapter(adapter: MarketDataAdapter):
    # 设置自定义适配器（用于测试）
    global _adapter_instance
    _adapter_instance = adapter
```

### 使用方式

#### API 服务中使用

```python
# 旧代码（直接依赖 ETL）
from etl.fetchers.snowball_client import get_stock_quote

quote = get_stock_quote(symbol)

# 新代码（通过适配器）
from app.adapters.factory import get_market_data_adapter

adapter = get_market_data_adapter()
quote = adapter.get_stock_quote(symbol)
```

#### 单元测试中使用

```python
from app.adapters.factory import set_market_data_adapter
from app.adapters.market_data_adapter import MarketDataAdapter
from app.adapters.mock_market_provider import MockMarketDataProvider

# 设置 Mock 提供者
test_data = {"stock_quote": {"600000.SH": {...}}}
mock_provider = MockMarketDataProvider(test_data)
mock_adapter = MarketDataAdapter(mock_provider)
set_market_data_adapter(mock_adapter)

# 测试代码不再依赖真实的 ETL 层
result = some_api_function()
```

## 优化效果

### 1. 解耦依赖

**优化前：**
- API 直接导入 ETL 模块
- 修改 ETL 可能影响 API
- 无法独立测试 API

**优化后：**
- API 只依赖适配器接口
- ETL 实现可以自由修改
- API 可以独立测试

### 2. 提高可测试性

**优化前：**
```python
# 测试必须依赖真实的 ETL 实现
def test_get_stock_profile():
    # 需要真实的数据库、网络请求等
    result = get_stock_profile("600000.SH")
```

**优化后：**
```python
# 测试使用 Mock 提供者
def test_get_stock_profile():
    set_market_data_adapter(mock_adapter)
    result = get_stock_profile("600000.SH")
    # 快速、可靠、无外部依赖
```

### 3. 支持多数据源

未来可以轻松添加新的数据源：

```python
# 添加新的提供者实现
class RestApiMarketProvider:
    """基于 REST API 的提供者"""
    def get_stock_quote(self, symbol):
        # 直接调用第三方 API
        return requests.get(f"https://api.example.com/quote/{symbol}").json()

# 切换到新提供者
provider = RestApiMarketProvider()
adapter = MarketDataAdapter(provider)
set_market_data_adapter(adapter)
```

### 4. 便于独立部署

```
部署方案 A（单体）：
┌──────────────────┐
│  API + ETL 一起  │
│  使用 ETL 提供者 │
└──────────────────┘

部署方案 B（微服务）：
┌──────────┐      ┌──────────┐
│   API    │ HTTP │   ETL    │
│使用 REST │─────→│  服务    │
│  提供者  │      │          │
└──────────┘      └──────────┘
```

## 迁移指南

### 步骤 1：更新导入

将所有直接导入 ETL 的代码改为使用适配器：

```python
# 旧代码
from etl.fetchers.snowball_client import get_stock_quote

# 新代码
from app.services.live_market_remote import get_stock_quote
# live_market_remote 内部使用适配器
```

### 步骤 2：更新测试

使用 Mock 提供者编写测试：

```python
from app.adapters.factory import set_market_data_adapter
from app.adapters.mock_market_provider import MockMarketDataProvider
from app.adapters.market_data_adapter import MarketDataAdapter

def setUp(self):
    mock_provider = MockMarketDataProvider(test_data)
    mock_adapter = MarketDataAdapter(mock_provider)
    set_market_data_adapter(mock_adapter)
```

### 步骤 3：验证功能

运行测试确保功能正常：

```bash
python -m unittest repo.tests.test_market_data_adapter -v
```

## 扩展性

### 添加新的数据源

1. 实现 `MarketDataProvider` 协议
2. 创建新的提供者类
3. 通过工厂函数切换

示例：

```python
# 1. 实现提供者
class DatabaseMarketProvider:
    """从数据库读取的提供者"""
    def get_stock_quote(self, symbol):
        # 从数据库查询
        return db.query(StockQuote).filter_by(symbol=symbol).first()

# 2. 注册提供者
provider = DatabaseMarketProvider()
adapter = MarketDataAdapter(provider)
set_market_data_adapter(adapter)
```

### 添加缓存层

可以在适配器中添加缓存装饰器：

```python
class CachedMarketDataAdapter(MarketDataAdapter):
    def get_stock_quote(self, symbol):
        cache_key = f"quote:{symbol}"
        cached = get_cache(cache_key)
        if cached:
            return cached
        
        result = super().get_stock_quote(symbol)
        set_cache(cache_key, result, ttl=60)
        return result
```

## 性能影响

### 额外开销

- 适配器调用增加 1 层函数调用
- 开销：< 0.1ms（可忽略）

### 性能优势

- 更容易实现缓存策略
- 支持批量优化
- 便于添加性能监控

## 总结

通过引入数据适配层，我们实现了：

✅ **解耦依赖**：API 不再直接依赖 ETL  
✅ **提高可测试性**：支持 Mock 数据源  
✅ **增强扩展性**：轻松添加新数据源  
✅ **支持独立部署**：API 和 ETL 可分离  
✅ **保持兼容性**：现有代码无需大改  

这是一个渐进式的重构方案，可以逐步迁移现有代码。
