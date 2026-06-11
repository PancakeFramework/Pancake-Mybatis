"""Pancake MyBatis Plus 插件 — 异步 ORM

支持 SQLite (aiosqlite)、PostgreSQL (asyncpg)、MySQL (aiomysql)。
通过 mybatis.database.url 自动选择驱动。
"""

import logging
from pancake.ovenware import InitAction

logger = logging.getLogger(__name__)

__all__ = [
    # Mapper
    "Mapper", "BaseMapper",
    # SQL 注解
    "Select", "SelectOne", "Insert", "Update", "Delete",
    # 链式查询
    "QueryWrapper", "UpdateWrapper", "qw", "uw",
    # 数据库
    "Database",
    # 事务
    "Transactional", "begin_transaction",
    # 分页
    "Page",
    # 自动建表
    "Table", "Column",
    # 异常
    "MyBatisError", "SqlParseError", "TransactionError",
    "MapperError", "DatabaseError", "PageError",
]


class Main(InitAction):
    """MyBatis 插件入口

    init_order=1, 在 embed(-10) 之后、web(50) 之前加载。
    提供 Mapper 注解、BaseMapper CRUD、链式查询、动态 SQL。
    """

    init_order = 1
    build_order = 0

    def __init__(self):
        from pancake.registry import export

        # Mapper 注解
        from pancake_mybatis.mapper import Mapper, BaseMapper
        export(Mapper)
        export(BaseMapper)

        # SQL 注解
        from pancake_mybatis.mapper import Select, SelectOne, Insert, Update, Delete
        export(Select)
        export(SelectOne)
        export(Insert)
        export(Update)
        export(Delete)

        # 链式查询
        from pancake_mybatis.wrapper import QueryWrapper, UpdateWrapper, qw, uw
        export(QueryWrapper)
        export(UpdateWrapper)
        export(qw)
        export(uw)

        # 数据库管理
        from pancake_mybatis.database import Database
        export(Database)

        # 事务
        from pancake_mybatis.transaction import Transactional, begin_transaction
        export(Transactional)
        export(begin_transaction)

        # 分页
        from pancake_mybatis.page import Page
        export(Page)

        # 自动建表
        from pancake_mybatis.schema import Table, Column
        export(Table)
        export(Column)

        # 异常
        from pancake_mybatis.exceptions import (
            MyBatisError, SqlParseError, TransactionError,
            MapperError, DatabaseError, PageError,
        )
        export(MyBatisError)
        export(SqlParseError)
        export(TransactionError)
        export(MapperError)
        export(DatabaseError)
        export(PageError)

        logger.info("MyBatis 插件已加载")

    def check(self) -> bool:
        from pancake import settings
        from pancake_mybatis.db_driver import detect_scheme

        url = settings.get("pancake.database.url", "sqlite:///resource/db/app.db")
        scheme = detect_scheme(url)

        driver_deps = {
            "sqlite": ("aiosqlite", "sqlite"),
            "postgresql": ("asyncpg", "postgres"),
            "mysql": ("aiomysql", "mysql"),
        }
        dep, extra = driver_deps.get(scheme, ("aiosqlite", "sqlite"))
        if not check_dependencies([dep], extras=extra):
            return False
        return True

    def build(self):
        pass
