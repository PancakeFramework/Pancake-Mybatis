"""数据库驱动抽象层 — 根据 URL 自动选择 SQLite/PostgreSQL/MySQL"""

import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class DriverBase(ABC):
    """驱动基类"""

    @abstractmethod
    async def connect(self, url: str, **kwargs):
        pass

    @abstractmethod
    async def close(self):
        pass

    @abstractmethod
    async def execute(self, sql: str, params=None):
        pass

    @abstractmethod
    async def fetch_all(self, sql: str, params=None) -> list:
        pass

    @abstractmethod
    async def fetch_one(self, sql: str, params=None):
        pass

    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass

    def placeholder(self, index: int) -> str:
        """占位符风格: SQLite/MySQL 用 ?, PG 用 $1"""
        return "?"

    def lastrowid(self, cursor) -> int:
        """获取自增 ID"""
        return cursor.lastrowid


# ── SQLite ──────────────────────────────────────────

class SQLiteDriver(DriverBase):
    def __init__(self):
        self._conn = None

    async def connect(self, url: str, **kwargs):
        import aiosqlite
        db_path = url
        if db_path.startswith("sqlite:///"):
            db_path = db_path[len("sqlite:///"):]
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = await aiosqlite.connect(db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        logger.info(f"[SQLite] 已连接: {db_path}")

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params=None):
        return await self._conn.execute(sql, params or ())

    async def fetch_all(self, sql: str, params=None) -> list:
        cursor = await self._conn.execute(sql, params or ())
        return await cursor.fetchall()

    async def fetch_one(self, sql: str, params=None):
        cursor = await self._conn.execute(sql, params or ())
        return await cursor.fetchone()

    async def commit(self):
        await self._conn.commit()

    async def rollback(self):
        await self._conn.rollback()


# ── PostgreSQL ──────────────────────────────────────

class PostgreSQLDriver(DriverBase):
    def __init__(self):
        self._pool = None

    async def connect(self, url: str, **kwargs):
        try:
            import asyncpg
        except ImportError:
            raise ImportError("PostgreSQL 驱动未安装，请运行: pip install pancake-mybatis[postgres]")
        min_size = kwargs.get("min_size", 1)
        max_size = kwargs.get("max_size", 5)
        self._pool = await asyncpg.create_pool(url, min_size=min_size, max_size=max_size)
        logger.info(f"[PostgreSQL] 连接池已创建")

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def execute(self, sql: str, params=None):
        async with self._pool.acquire() as conn:
            return await conn.execute(sql, *(params or ()))

    async def fetch_all(self, sql: str, params=None) -> list:
        async with self._pool.acquire() as conn:
            return await conn.fetch(sql, *(params or ()))

    async def fetch_one(self, sql: str, params=None):
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, *(params or ()))

    async def commit(self):
        pass  # asyncpg 每条语句自动提交

    async def rollback(self):
        pass

    def placeholder(self, index: int) -> str:
        return f"${index}"

    def lastrowid(self, result) -> int:
        if hasattr(result, "split"):
            # INSERT ... RETURNING id 的结果
            parts = result.split()
            if parts:
                try:
                    return int(parts[-1])
                except ValueError:
                    pass
        return 0


# ── MySQL ──────────────────────────────────────────

class MySQLDriver(DriverBase):
    def __init__(self):
        self._conn = None

    async def connect(self, url: str, **kwargs):
        try:
            import aiomysql
        except ImportError:
            raise ImportError("MySQL 驱动未安装，请运行: pip install pancake-mybatis[mysql]")
        from urllib.parse import urlparse
        parsed = urlparse(url)
        self._conn = await aiomysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            db=parsed.path.lstrip("/"),
            autocommit=False,
        )
        logger.info(f"[MySQL] 已连接: {parsed.hostname}:{parsed.port}")

    async def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params=None):
        async with self._conn.cursor() as cursor:
            await cursor.execute(sql, params or ())
            return cursor

    async def fetch_all(self, sql: str, params=None) -> list:
        async with self._conn.cursor() as cursor:
            await cursor.execute(sql, params or ())
            return await cursor.fetchall()

    async def fetch_one(self, sql: str, params=None):
        async with self._conn.cursor() as cursor:
            await cursor.execute(sql, params or ())
            return await cursor.fetchone()

    async def commit(self):
        await self._conn.commit()

    async def rollback(self):
        await self._conn.rollback()


# ── 工厂 ──────────────────────────────────────────

_DRIVER_MAP = {
    "sqlite": SQLiteDriver,
    "postgresql": PostgreSQLDriver,
    "postgres": PostgreSQLDriver,
    "mysql": MySQLDriver,
}


def detect_scheme(url: str) -> str:
    """从 URL 检测数据库类型"""
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("postgres"):
        return "postgresql"
    if url.startswith("mysql"):
        return "mysql"
    return "sqlite"


def create_driver(url: str) -> DriverBase:
    """根据 URL 创建对应驱动"""
    scheme = detect_scheme(url)
    cls = _DRIVER_MAP.get(scheme)
    if cls is None:
        raise ValueError(f"不支持的数据库: {scheme}")
    return cls()
