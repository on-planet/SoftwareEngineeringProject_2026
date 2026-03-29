#!/usr/bin/env python
"""验证数据库连接池优化"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from etl.utils.db_pool import get_engine, get_session_factory, dispose_all_engines

def main():
    """验证连接池单例模式"""
    print("=" * 60)
    print("数据库连接池优化验证")
    print("=" * 60)
    
    test_url = "postgresql://test:test@localhost/test"
    
    # 测试 1: 相同配置返回同一个引擎
    print("\n测试 1: 相同配置返回同一个引擎实例")
    engine1 = get_engine(test_url, pool_size=5, max_overflow=5)
    engine2 = get_engine(test_url, pool_size=5, max_overflow=5)
    
    if engine1 is engine2:
        print("✅ 通过：相同配置返回同一个引擎实例")
    else:
        print("❌ 失败：应该返回同一个引擎实例")
        return False
    
    # 测试 2: 不同配置创建不同引擎
    print("\n测试 2: 不同配置创建不同引擎实例")
    engine3 = get_engine(test_url, pool_size=10, max_overflow=10)
    
    if engine1 is not engine3:
        print("✅ 通过：不同配置创建不同引擎实例")
    else:
        print("❌ 失败：应该创建不同的引擎实例")
        return False
    
    # 测试 3: Session 工厂单例
    print("\n测试 3: Session 工厂单例模式")
    factory1 = get_session_factory(test_url, pool_size=5)
    factory2 = get_session_factory(test_url, pool_size=5)
    
    if factory1 is factory2:
        print("✅ 通过：相同配置返回同一个 Session 工厂")
    else:
        print("❌ 失败：应该返回同一个 Session 工厂")
        return False
    
    # 测试 4: 清理引擎
    print("\n测试 4: 清理所有缓存的引擎")
    dispose_all_engines()
    print("✅ 通过：成功清理所有引擎")
    
    # 测试 5: 清理后重新创建
    print("\n测试 5: 清理后重新创建引擎")
    engine4 = get_engine(test_url, pool_size=5, max_overflow=5)
    
    if engine4 is not engine1:
        print("✅ 通过：清理后创建新的引擎实例")
    else:
        print("❌ 失败：应该创建新的引擎实例")
        return False
    
    print("\n" + "=" * 60)
    print("所有测试通过！✅")
    print("=" * 60)
    
    # 清理
    dispose_all_engines()
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as exc:
        print(f"\n❌ 验证失败: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
