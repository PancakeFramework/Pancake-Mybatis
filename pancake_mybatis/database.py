"""数据库连接管理 — 多数据库驱动自动选择"""

import logging
from pancake.base import Service

logger = logging.getLogger(__name__)


class Database(Service):
    """数据库连接管理器

    根据 URL 自动选择驱动:
        sqlite:///path       → aiosqlite
        postgresql://...     → asyncpg
        mysql://...          → aiomysql

    配置项:
        mybatis.database.url:        数据库 URL (默认 sqlite:///resource/db/app.db)
        mybatis.database.min_size:   连接池最小 (默认 1)
        mybatis.database.max_size:   连接池最大 (默认 5)
    """

    _defaults = {
        "mybatis.database.url": "sqlite:///resource/db/app.db",
        "mybatis.database.min_size": 1,
        "mybatis.database.max_size": 5,
    }

    def _get(self, key):
        from pancake import settings
        val = settings.get(key)
        return val if val is not None else self._defaults.get(key)

    def __init__(self):
        super().__init__()
        self.url = self._get("mybatis.database.url")
        self.min_size = int(self._get("mybatis.database.min_size"))
        self.max_size = int(self._get("mybatis.database.max_size"))
        self._driver = None

    async def on_init(self):
        from pancake_mybatis.db_driver import create_driver
        self._driver = create_driver(self.url)
        await self._driver.connect(
            self.url, min_size=self.min_size, max_size=self.max_size
        )

    async def on_destroy(self):
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("数据库已断开")

    @property
    def driver(self):
        """获取底层驱动实例"""
        return self._driver

    async def execute(self, sql: str, params=None):
        return await self._driver.execute(sql, params)

    async def fetch_all(self, sql: str, params=None) -> list:
        return await self._driver.fetch_all(sql, params)

    async def fetch_one(self, sql: str, params=None):
        return await self._driver.fetch_one(sql, params)

    async def commit(self):
        await self._driver.commit()

    async def rollback(self):
        await self._driver.rollback()
