"""自动建表 — @Table / @Column 注解"""

import logging
from dataclasses import fields

logger = logging.getLogger(__name__)

# Python 类型 → SQLite 类型映射
_TYPE_MAP = {
    int: "INTEGER",
    float: "REAL",
    str: "TEXT",
    bool: "INTEGER",  # SQLite 无布尔，用 0/1
    bytes: "BLOB",
}


def Table(name: str = None, auto_create: bool = True):
    """@Table — 标记 dataclass 为数据库表，支持自动建表

    用法:
        @Table("users")
        @dataclass
        class User(Struct):
            id: int = None
            name: str = None
            age: int = None

        # 或不指定表名，自动用类名小写
        @Table()
        @dataclass
        class User(Struct): ...
    """
    def decorator(cls):
        table_name = name or cls.__name__.lower()
        cls._table_name = table_name
        cls._auto_create = auto_create
        return cls
    return decorator


def Column(primary_key: bool = False, autoincrement: bool = False,
           nullable: bool = True, default=None):
    """@Column — 标记字段的列属性

    用法:
        @dataclass
        class User(Struct):
            id: int = Column(primary_key=True, autoincrement=True)
            name: str = Column(nullable=False)
            age: int = Column(default=0)
    """
    return _ColumnMeta(
        primary_key=primary_key,
        autoincrement=autoincrement,
        nullable=nullable,
        default=default,
    )


class _ColumnMeta:
    """Column 元数据（用作字段 default 值的标记）"""
    def __init__(self, primary_key=False, autoincrement=False, nullable=True, default=None):
        self.primary_key = primary_key
        self.autoincrement = autoincrement
        self.nullable = nullable
        self.default = default


def generate_create_sql(entity_class) -> str:
    """根据 Struct 子类生成 CREATE TABLE IF NOT EXISTS SQL"""
    table_name = getattr(entity_class, "_table_name", entity_class.__name__.lower())
    columns = []
    pk_col = None

    for f in fields(entity_class):
        col_name = f.name
        col_meta = f.default if isinstance(f.default, _ColumnMeta) else None

        # 类型映射
        col_type = _TYPE_MAP.get(f.type if isinstance(f.type, type) else str, "TEXT")

        # 主键
        if col_meta and col_meta.primary_key:
            pk_col = col_name
            if col_meta.autoincrement:
                columns.append(f"    {col_name} INTEGER PRIMARY KEY AUTOINCREMENT")
            else:
                columns.append(f"    {col_name} {col_type} PRIMARY KEY")
            continue

        # 非空
        nullable = "" if (col_meta and not col_meta.nullable) else ""
        not_null = " NOT NULL" if (col_meta and not col_meta.nullable) else ""

        # 默认值
        default_val = ""
        if col_meta and col_meta.default is not None:
            default_val = f" DEFAULT {col_meta.default!r}"

        columns.append(f"    {col_name} {col_type}{not_null}{default_val}")

    if pk_col is None:
        columns.insert(0, "    id INTEGER PRIMARY KEY AUTOINCREMENT")

    cols_sql = ",\n".join(columns)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n{cols_sql}\n)"


async def create_table(entity_class):
    """根据 entity 类自动建表"""
    from pancake.factory.dough_factory import DoughFactory
    db = DoughFactory.get().resolve("Database")

    sql = generate_create_sql(entity_class)
    logger.info(f"自动建表:\n{sql}")
    await db.execute(sql)
    await db.commit()
