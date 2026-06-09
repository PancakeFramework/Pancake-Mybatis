"""数据库连接管理 — aiosqlite"""

import logging
import os
import aiosqlite
from pancake.base import Service

logger = logging.getLogger(__name__)


class Database(Service):
    """数据库连接管理器

    从 settings 读取 mybatis.database.* 配置。
    pool_size=1 时使用单连接，>1 时使用连接池。

    配置项:
        mybatis.database.url:       数据库路径 (默认 resource/db/app.db)
        mybatis.database.pool_size: 连接池大小 (默认 1)
    """

    _defaults = {
        "mybatis.database.url": "resource/db/app.db",
        "mybatis.database.pool_size": 1,
    }

    def _get(self, key):
        from pancake import settings
        val = settings.get(key)
        return val if val is not None else self._defaults.get(key)

    def __init__(self):
        super().__init__()
        self.url = self._get("mybatis.database.url")
        self.pool_size = int(self._get("mybatis.database.pool_size"))
        self._conn = None
        self._pool = None

    async def on_init(self):
        db_path = self.url
        if db_path.startswith("sqlite:///"):
            db_path = db_path[len("sqlite:///"):]
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        if self.pool_size > 1:
            from pancake_mybatis.pool import SQLitePool
            self._pool = SQLitePool(db_path, self.pool_size)
            await self._pool.init()
            logger.info(f"数据库连接池已初始化: {db_path}, pool_size={self.pool_size}")
        else:
            self._conn = await aiosqlite.connect(db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            logger.info(f"数据库已连接: {db_path}")

    async def on_destroy(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("数据库连接池已关闭")
        elif self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("数据库已断开")

    @property
    def connection(self) -> aiosqlite.Connection:
        """获取单连接（仅 pool_size=1 时可用）"""
        return self._conn

    async def execute(self, sql: str, params=None) -> aiosqlite.Cursor:
        """执行 SQL"""
        if self._pool:
            return await self._pool.execute(sql, params)
        return await self._conn.execute(sql, params or ())

    async def fetch_all(self, sql: str, params=None) -> list[aiosqlite.Row]:
        """查询多条"""
        if self._pool:
            return await self._pool.fetch_all(sql, params)
        cursor = await self._conn.execute(sql, params or ())
        return await cursor.fetchall()

    async def fetch_one(self, sql: str, params=None) -> aiosqlite.Row | None:
        """查询单条"""
        if self._pool:
            return await self._pool.fetch_one(sql, params)
        cursor = await self._conn.execute(sql, params or ())
        return await cursor.fetchone()

    async def commit(self):
        """提交事务"""
        if not self._pool:
            await self._conn.commit()
