"""Mapper 基类和 SQL 注解"""

import inspect
import logging
from dataclasses import fields, asdict
from pancake.base import Service
from pancake_mybatis.sql_parser import parse_sql, parse_dynamic_sql, convert_placeholders, validate_identifier

logger = logging.getLogger(__name__)


# ── SQL 注解 ──────────────────────────────────────────

def Select(sql: str):
    """@Select — 查询多条记录"""
    def decorator(func):
        func._sql = sql
        func._sql_type = "select"
        return func
    return decorator


def SelectOne(sql: str):
    """@SelectOne — 查询单条记录"""
    def decorator(func):
        func._sql = sql
        func._sql_type = "select_one"
        return func
    return decorator


def Insert(sql: str):
    """@Insert — 插入记录"""
    def decorator(func):
        func._sql = sql
        func._sql_type = "insert"
        return func
    return decorator


def Update(sql: str):
    """@Update — 更新记录"""
    def decorator(func):
        func._sql = sql
        func._sql_type = "update"
        return func
    return decorator


def Delete(sql: str):
    """@Delete — 删除记录"""
    def decorator(func):
        func._sql = sql
        func._sql_type = "delete"
        return func
    return decorator


# ── Mapper 注解 ──────────────────────────────────────

def Mapper(cls):
    """@Mapper — 标记类为 Mapper，自动注册为 Service 子类"""
    from pancake.decorators.convert import _convert_class
    cls = _convert_class(cls, BaseMapper, dough_type="mapper")
    return cls


# ── BaseMapper ──────────────────────────────────────

class BaseMapper(Service):
    """Mapper 基类 — 提供内置 CRUD 方法

    子类定义:
        _entity_class: Struct/dataclass 类型
        _table_name: 表名
    """

    _entity_class = None
    _table_name = ""

    def _table(self) -> str:
        """校验并返回表名"""
        validate_identifier(self._table_name)
        return self._table_name

    def _ph(self, n: int = 1, start: int = 1) -> str:
        """生成占位符: SQLite/MySQL → ?,?,?, PG → $1,$2,$3"""
        db = self._get_db()
        style = "pg" if hasattr(db.driver, "placeholder") and db.driver.placeholder(1).startswith("$") else "q"
        if style == "pg":
            return ", ".join(f"${i}" for i in range(start, start + n))
        return ", ".join(["?"] * n)

    async def on_init(self):
        """初始化时包装所有带 SQL 注解的方法"""
        self._wrap_annotated_methods()

    def _wrap_annotated_methods(self):
        """将带 _sql/_sql_type 标记的方法包装为自动执行"""
        for name in dir(self):
            if name.startswith("_"):
                continue
            method = getattr(self, name, None)
            if method is None or not hasattr(method, "_sql"):
                continue
            wrapped = self._create_sql_executor(method)
            setattr(self, name, wrapped)

    def _create_sql_executor(self, method):
        """为注解方法创建自动执行包装器"""
        import functools

        sql_template = method._sql
        sql_type = method._sql_type
        sig = inspect.signature(method)
        mapper_self = self

        @functools.wraps(method)
        async def executor(*args, **kwargs):
            # 绑定参数
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            params = {k: v for k, v in bound.arguments.items() if k != "self"}

            # 解析动态 SQL
            sql = parse_dynamic_sql(sql_template, params)
            # #{param} → ? 占位符
            parsed_sql, values = parse_sql(sql, params)

            # 根据驱动转换占位符风格
            db = mapper_self._get_db()
            driver = db.driver
            if hasattr(driver, "placeholder") and driver.placeholder(1).startswith("$"):
                parsed_sql = convert_placeholders(parsed_sql, "pg")

            logger.debug(f"SQL: {parsed_sql} | params: {values}")

            if sql_type == "select":
                rows = await db.fetch_all(parsed_sql, tuple(values))
                return mapper_self._rows_to_entities(rows)
            elif sql_type == "select_one":
                row = await db.fetch_one(parsed_sql, tuple(values))
                return mapper_self._row_to_entity(row)
            elif sql_type == "insert":
                if hasattr(driver, "placeholder") and driver.placeholder(1).startswith("$"):
                    parsed_sql += " RETURNING id"
                    row = await db.fetch_one(parsed_sql, tuple(values))
                    return row["id"] if row else 0
                cursor = await db.execute(parsed_sql, tuple(values))
                await db.commit()
                return cursor.lastrowid
            elif sql_type in ("update", "delete"):
                cursor = await db.execute(parsed_sql, tuple(values))
                await db.commit()
                return cursor.rowcount

        executor._sql = sql_template
        executor._sql_type = sql_type
        return executor

    def _get_db(self) -> "Database":
        from pancake.factory.dough_factory import DoughFactory
        return DoughFactory.get().resolve("Database")

    def _row_to_entity(self, row) -> object:
        """aiosqlite.Row → Struct 实例（含类型转换）"""
        if row is None or self._entity_class is None:
            return row
        data = dict(row)
        # 按 dataclass 字段类型做转换
        for f in fields(self._entity_class):
            if f.name in data and data[f.name] is not None:
                ft = f.type if isinstance(f.type, type) else str
                try:
                    if ft is bool:
                        data[f.name] = bool(int(data[f.name]))
                    elif ft in (int, float, str):
                        data[f.name] = ft(data[f.name])
                except (ValueError, TypeError):
                    pass
        return self._entity_class(**data)

    def _rows_to_entities(self, rows: list) -> list:
        """批量转换"""
        return [self._row_to_entity(r) for r in rows]

    async def select_by_id(self, id):
        db = self._get_db()
        row = await db.fetch_one(
            f"SELECT * FROM {self._table()} WHERE id = {self._ph()}", (id,)
        )
        return self._row_to_entity(row)

    async def select_list(self, **kwargs):
        db = self._get_db()
        table = self._table()
        if kwargs:
            for k in kwargs:
                validate_identifier(k)
            cols = " AND ".join(f"{k} = {self._ph()}" for k in kwargs)
            sql = f"SELECT * FROM {table} WHERE {cols}"
            rows = await db.fetch_all(sql, tuple(kwargs.values()))
        else:
            rows = await db.fetch_all(f"SELECT * FROM {table}")
        return self._rows_to_entities(rows)

    async def select_one(self, **kwargs):
        db = self._get_db()
        for k in kwargs:
            validate_identifier(k)
        cols = " AND ".join(f"{k} = {self._ph()}" for k in kwargs)
        row = await db.fetch_one(
            f"SELECT * FROM {self._table()} WHERE {cols}", tuple(kwargs.values())
        )
        return self._row_to_entity(row)

    async def select_count(self, **kwargs) -> int:
        db = self._get_db()
        table = self._table()
        if kwargs:
            for k in kwargs:
                validate_identifier(k)
            cols = " AND ".join(f"{k} = {self._ph()}" for k in kwargs)
            row = await db.fetch_one(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE {cols}",
                tuple(kwargs.values()),
            )
        else:
            row = await db.fetch_one(
                f"SELECT COUNT(*) as cnt FROM {table}"
            )
        return row["cnt"] if row else 0

    async def insert(self, entity=None, **kwargs) -> int:
        from dataclasses import asdict, is_dataclass
        if entity is not None and is_dataclass(entity):
            kwargs = {k: v for k, v in asdict(entity).items() if v is not None}
        db = self._get_db()
        for k in kwargs:
            validate_identifier(k)
        cols = ", ".join(kwargs.keys())
        placeholders = self._ph(len(kwargs))
        sql = f"INSERT INTO {self._table()} ({cols}) VALUES ({placeholders})"
        if hasattr(db.driver, "placeholder") and db.driver.placeholder(1).startswith("$"):
            sql += " RETURNING id"
            row = await db.fetch_one(sql, tuple(kwargs.values()))
            return row["id"] if row else 0
        cursor = await db.execute(sql, tuple(kwargs.values()))
        await db.commit()
        return cursor.lastrowid

    async def insert_batch(self, entities: list) -> int:
        if not entities:
            return 0
        db = self._get_db()
        first = asdict(entities[0]) if hasattr(entities[0], "__dataclass_fields__") else entities[0]
        for k in first.keys():
            validate_identifier(k)
        cols = ", ".join(first.keys())
        placeholders = self._ph(len(first))
        sql = f"INSERT INTO {self._table()} ({cols}) VALUES ({placeholders})"
        rows = [
            tuple(asdict(e).values() if hasattr(e, "__dataclass_fields__") else e.values())
            for e in entities
        ]
        for row in rows:
            await db.execute(sql, row)
        await db.commit()
        return len(rows)

    async def update_by_id(self, id, **kwargs) -> int:
        db = self._get_db()
        for k in kwargs:
            validate_identifier(k)
        sets = ", ".join(f"{k} = {self._ph()}" for k in kwargs)
        values = list(kwargs.values()) + [id]
        ph = self._ph()
        cursor = await db.execute(
            f"UPDATE {self._table()} SET {sets} WHERE id = {ph}", tuple(values)
        )
        await db.commit()
        return cursor.rowcount

    async def delete_by_id(self, id) -> int:
        db = self._get_db()
        cursor = await db.execute(
            f"DELETE FROM {self._table()} WHERE id = {self._ph()}", (id,)
        )
        await db.commit()
        return cursor.rowcount

    async def select(self, wrapper) -> list:
        db = self._get_db()
        where, params = wrapper.build_where()
        order = wrapper.build_order()
        limit = wrapper.build_limit()
        sql = f"SELECT * FROM {self._table()} {where} {order} {limit}".strip()
        sql = self._convert_sql(sql)
        rows = await db.fetch_all(sql, tuple(params))
        return self._rows_to_entities(rows)

    async def select_page(self, page, wrapper=None) -> "Page":
        """分页查询"""
        from pancake_mybatis.page import Page
        db = self._get_db()

        where, params = ("", [])
        order = ""
        if wrapper:
            where, params = wrapper.build_where()
            order = wrapper.build_order()

        table = self._table()
        count_sql = f"SELECT COUNT(*) as cnt FROM {table} {where}".strip()
        row = await db.fetch_one(count_sql, tuple(params))
        page.total = row["cnt"] if row else 0

        offset = page.offset
        ph1 = self._ph()
        ph2 = self._ph()
        data_sql = f"SELECT * FROM {table} {where} {order} LIMIT {ph1} OFFSET {ph2}".strip()
        rows = await db.fetch_all(data_sql, tuple(params) + (page.size, offset))
        page.records = self._rows_to_entities(rows)
        return page

    async def update(self, wrapper) -> int:
        db = self._get_db()
        set_sql, set_params = wrapper.build_set()
        where_sql, where_params = wrapper.build_where()
        sql = f"UPDATE {self._table()} {set_sql} {where_sql}".strip()
        sql = self._convert_sql(sql)
        cursor = await db.execute(sql, tuple(set_params + where_params))
        await db.commit()
        return cursor.rowcount

    async def delete(self, wrapper) -> int:
        db = self._get_db()
        where, params = wrapper.build_where()
        sql = f"DELETE FROM {self._table()} {where}".strip()
        sql = self._convert_sql(sql)
        cursor = await db.execute(sql, tuple(params))
        await db.commit()
        return cursor.rowcount

    def _convert_sql(self, sql: str) -> str:
        """根据驱动转换占位符风格"""
        db = self._get_db()
        if hasattr(db.driver, "placeholder") and db.driver.placeholder(1).startswith("$"):
            return convert_placeholders(sql, "pg")
        return sql
