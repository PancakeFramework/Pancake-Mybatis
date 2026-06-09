"""pancake-mybatis 插件测试"""

import sys
import os
import asyncio

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_sql_parser():
    """测试 SQL 解析器"""
    from pancake_mybatis.sql_parser import parse_sql, parse_dynamic_sql

    # #{param} → ?
    sql, values = parse_sql("SELECT * FROM users WHERE name = #{name} AND age > #{age}", {"name": "Alice", "age": 18})
    assert sql == "SELECT * FROM users WHERE name = ? AND age > ?", f"Got: {sql}"
    assert values == ["Alice", 18], f"Got: {values}"

    # <if>
    sql = parse_dynamic_sql("SELECT * FROM users <if test=\"name\">WHERE name = #{name}</if>", {"name": "Alice"})
    assert "WHERE name" in sql, f"Got: {sql}"

    sql = parse_dynamic_sql("SELECT * FROM users <if test=\"name\">WHERE name = #{name}</if>", {})
    assert "WHERE" not in sql, f"Got: {sql}"

    # <where>
    sql = parse_dynamic_sql("SELECT * FROM users <where>AND name = #{name}</where>", {"name": "Alice"})
    assert "WHERE name" in sql, f"Got: {sql}"

    # <choose>/<when>/<otherwise>
    sql = parse_dynamic_sql(
        "SELECT * FROM users <choose><when test=\"order\">ORDER BY age</when><otherwise>ORDER BY id</otherwise></choose>",
        {"order": True}
    )
    assert "ORDER BY age" in sql, f"Got: {sql}"

    sql = parse_dynamic_sql(
        "SELECT * FROM users <choose><when test=\"order\">ORDER BY age</when><otherwise>ORDER BY id</otherwise></choose>",
        {}
    )
    assert "ORDER BY id" in sql, f"Got: {sql}"

    print("[PASS] sql_parser")


def test_wrapper():
    """测试链式查询构造器"""
    from pancake_mybatis.wrapper import qw, uw

    # QueryWrapper
    w = qw().eq("name", "Alice").ge("age", 18).order_by_desc("age").limit(10)
    where, params = w.build_where()
    assert "WHERE" in where, f"Got: {where}"
    assert params == ["Alice", 18], f"Got: {params}"
    assert "ORDER BY age DESC" in w.build_order(), f"Got: {w.build_order()}"
    assert "LIMIT 10" in w.build_limit(), f"Got: {w.build_limit()}"

    # IN
    w = qw().in_("status", [1, 2, 3])
    where, params = w.build_where()
    assert "IN" in where, f"Got: {where}"
    assert params == [1, 2, 3], f"Got: {params}"

    # IS NULL
    w = qw().is_null("deleted_at")
    where, _ = w.build_where()
    assert "IS NULL" in where, f"Got: {where}"

    # BETWEEN
    w = qw().between("age", 18, 30)
    where, params = w.build_where()
    assert "BETWEEN" in where, f"Got: {where}"
    assert params == [18, 30], f"Got: {params}"

    # UpdateWrapper
    u = uw().set("name", "Bob").eq("id", 1)
    set_sql, set_params = u.build_set()
    where_sql, where_params = u.build_where()
    assert "SET name = ?" in set_sql, f"Got: {set_sql}"
    assert set_params == ["Bob"], f"Got: {set_params}"
    assert "WHERE id = ?" in where_sql, f"Got: {where_sql}"
    assert where_params == [1], f"Got: {where_params}"

    print("✓ wrapper 测试通过")


def test_page():
    """测试分页对象"""
    from pancake_mybatis.page import Page

    page = Page(current=2, size=20)
    assert page.offset == 20, f"Got: {page.offset}"

    page.total = 100
    assert page.pages == 5, f"Got: {page.pages}"
    assert page.has_next is True
    assert page.has_prev is True

    page = Page(current=1, size=20)
    page.total = 100
    assert page.has_prev is False

    page = Page(current=5, size=20)
    page.total = 100
    assert page.has_next is False

    # 边界
    page = Page(current=0, size=-1)
    assert page.current == 1
    assert page.size == 20

    print("✓ page 测试通过")


def test_exceptions():
    """测试异常类"""
    from pancake_mybatis.exceptions import (
        MyBatisError, SqlParseError, TransactionError,
        MapperError, DatabaseError, PageError,
    )

    assert issubclass(SqlParseError, MyBatisError)
    assert issubclass(TransactionError, MyBatisError)
    assert issubclass(MapperError, MyBatisError)
    assert issubclass(DatabaseError, MyBatisError)
    assert issubclass(PageError, MyBatisError)

    try:
        raise SqlParseError("test")
    except MyBatisError as e:
        assert str(e) == "test"

    print("✓ exceptions 测试通过")


def test_schema():
    """测试自动建表"""
    from dataclasses import dataclass
    from pancake_mybatis.schema import Table, Column, generate_create_sql

    @Table("users")
    @dataclass
    class User:
        id: int = Column(primary_key=True, autoincrement=True)
        name: str = Column(nullable=False)
        age: int = Column(default=0)

    sql = generate_create_sql(User)
    assert "CREATE TABLE IF NOT EXISTS users" in sql, f"Got: {sql}"
    assert "id INTEGER PRIMARY KEY AUTOINCREMENT" in sql, f"Got: {sql}"
    assert "name TEXT NOT NULL" in sql, f"Got: {sql}"
    assert "age INTEGER" in sql, f"Got: {sql}"

    # 默认表名
    @Table()
    @dataclass
    class OrderItem:
        id: int = Column(primary_key=True, autoincrement=True)

    sql = generate_create_sql(OrderItem)
    assert "orderitem" in sql.lower(), f"Got: {sql}"

    print("✓ schema 测试通过")


def test_mapper_annotations():
    """测试 Mapper 注解标记"""
    from pancake_mybatis.mapper import Select, SelectOne, Insert, Update, Delete

    @Select("SELECT * FROM users WHERE id = #{id}")
    async def find_by_id(id): ...

    @Insert("INSERT INTO users (name) VALUES (#{name})")
    async def add_user(name): ...

    assert hasattr(find_by_id, "_sql")
    assert find_by_id._sql_type == "select"
    assert hasattr(add_user, "_sql")
    assert add_user._sql_type == "insert"

    print("✓ mapper annotations 测试通过")


def test_transaction_decorator():
    """测试事务装饰器结构"""
    from pancake_mybatis.transaction import Transactional, begin_transaction

    @Transactional()
    async def do_something(): ...

    assert hasattr(do_something, "_transactional")
    assert do_something._transactional is True

    # begin_transaction 返回上下文管理器
    ctx = begin_transaction()
    assert hasattr(ctx, "__aenter__")
    assert hasattr(ctx, "__aexit__")

    print("✓ transaction 测试通过")


if __name__ == "__main__":
    test_sql_parser()
    test_wrapper()
    test_page()
    test_exceptions()
    test_schema()
    test_mapper_annotations()
    test_transaction_decorator()
    print("\n✅ 全部测试通过")
