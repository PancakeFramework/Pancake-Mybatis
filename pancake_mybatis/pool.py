"""连接池 — 基于 aiosqlite 的简单连接池"""

import asyncio
import logging
import aiosqlite

logger = logging.getLogger(__name__)


class SQLitePool:
    """aiosqlite 连接池

    SQLite 是文件级数据库，通过 WAL 模式 + 连接池提升并发读性能。
    写操作自动串行化（SQLite 限制）。
    """

    def __init__(self, db_path: str, pool_size: int = 5):
        self._db_path = db_path
        self._pool_size = pool_size
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=pool_size)
        self._size = 0
        self._closed = False

    async def _create_connection(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        return conn

    async def init(self):
        """初始化连接池"""
        for _ in range(self._pool_size):
            conn = await self._create_connection()
            await self._pool.put(conn)
            self._size += 1
        logger.info(f"连接池已初始化: {self._db_path}, size={self._pool_size}")

    async def acquire(self) -> aiosqlite.Connection:
        """获取连接"""
        if self._closed:
            raise RuntimeError("连接池已关闭")
        return await self._pool.get()

    async def release(self, conn: aiosqlite.Connection):
        """归还连接"""
        if self._closed:
            await conn.close()
            return
        await self._pool.put(conn)

    async def close(self):
        """关闭所有连接"""
        self._closed = True
        while not self._pool.empty():
            conn = await self._pool.get()
            await conn.close()
            self._size -= 1
        logger.info("连接池已关闭")

    async def execute(self, sql: str, params=None):
        conn = await self.acquire()
        try:
            cursor = await conn.execute(sql, params or ())
            await conn.commit()
            return cursor
        finally:
            await self.release(conn)

    async def fetch_all(self, sql: str, params=None) -> list:
        conn = await self.acquire()
        try:
            cursor = await conn.execute(sql, params or ())
            return await cursor.fetchall()
        finally:
            await self.release(conn)

    async def fetch_one(self, sql: str, params=None):
        conn = await self.acquire()
        try:
            cursor = await conn.execute(sql, params or ())
            return await cursor.fetchone()
        finally:
            await self.release(conn)
