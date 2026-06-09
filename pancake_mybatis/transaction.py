"""事务支持 — @Transactional 装饰器"""

import functools
import logging

logger = logging.getLogger(__name__)


def Transactional(rollback_on: tuple = (Exception,)):
    """@Transactional — 声明式事务

    用法:
        @Transactional()
        async def transfer(self, from_id, to_id, amount):
            await self.update_by_id(from_id, balance=...)
            await self.update_by_id(to_id, balance=...)

        @Transactional(rollback_on=(ValueError,))
        async def only_rollback_on_value_error(self):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from pancake.factory.dough_factory import DoughFactory
            db = DoughFactory.get().resolve("Database")
            conn = db.connection

            try:
                await conn.execute("BEGIN")
                result = await func(*args, **kwargs)
                await conn.commit()
                logger.debug(f"事务提交: {func.__qualname__}")
                return result
            except rollback_on as e:
                await conn.rollback()
                logger.warning(f"事务回滚: {func.__qualname__} — {e}")
                raise

        wrapper._transactional = True
        return wrapper
    return decorator


def begin_transaction():
    """手动开启事务（上下文管理器）

    用法:
        async with begin_transaction() as db:
            await db.execute("INSERT ...")
            await db.execute("UPDATE ...")
    """
    return _TransactionContext()


class _TransactionContext:
    async def __aenter__(self):
        from pancake.factory.dough_factory import DoughFactory
        self._db = DoughFactory.get().resolve("Database")
        await self._db.connection.execute("BEGIN")
        return self._db

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self._db.connection.rollback()
            logger.warning(f"事务回滚: {exc_val}")
        else:
            await self._db.connection.commit()
            logger.debug("事务提交")
        return False
