"""链式查询构造器 — QueryWrapper / UpdateWrapper"""

from pancake_mybatis.sql_parser import validate_identifier


class QueryWrapper:
    """查询条件构造器

    Usage:
        qw().ge("age", 18).like("name", "%Ali%").order_by_desc("age").limit(50)
    """

    def __init__(self):
        self._conditions = []
        self._order_by = []
        self._limit_val = None
        self._offset_val = None

    def eq(self, col, val):
        self._conditions.append((col, "=", val))
        return self

    def ne(self, col, val):
        self._conditions.append((col, "!=", val))
        return self

    def gt(self, col, val):
        self._conditions.append((col, ">", val))
        return self

    def ge(self, col, val):
        self._conditions.append((col, ">=", val))
        return self

    def lt(self, col, val):
        self._conditions.append((col, "<", val))
        return self

    def le(self, col, val):
        self._conditions.append((col, "<=", val))
        return self

    def like(self, col, val):
        self._conditions.append((col, "LIKE", val))
        return self

    def in_(self, col, values):
        self._conditions.append((col, "IN", values))
        return self

    def between(self, col, a, b):
        self._conditions.append((col, "BETWEEN", (a, b)))
        return self

    def is_null(self, col):
        self._conditions.append((col, "IS NULL", None))
        return self

    def is_not_null(self, col):
        self._conditions.append((col, "IS NOT NULL", None))
        return self

    def order_by_asc(self, col):
        self._order_by.append((col, "ASC"))
        return self

    def order_by_desc(self, col):
        self._order_by.append((col, "DESC"))
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    def offset(self, n):
        self._offset_val = n
        return self

    def build_where(self) -> tuple[str, list]:
        if not self._conditions:
            return "", []
        parts = []
        params = []
        for col, op, val in self._conditions:
            validate_identifier(col)
            if op == "IS NULL":
                parts.append(f"{col} IS NULL")
            elif op == "IS NOT NULL":
                parts.append(f"{col} IS NOT NULL")
            elif op == "IN":
                placeholders = ", ".join(["?" for _ in val])
                parts.append(f"{col} IN ({placeholders})")
                params.extend(val)
            elif op == "BETWEEN":
                parts.append(f"{col} BETWEEN ? AND ?")
                params.extend(val)
            else:
                parts.append(f"{col} {op} ?")
                params.append(val)
        return "WHERE " + " AND ".join(parts), params

    def build_order(self) -> str:
        if not self._order_by:
            return ""
        for col, _ in self._order_by:
            validate_identifier(col)
        parts = [f"{col} {d}" for col, d in self._order_by]
        return "ORDER BY " + ", ".join(parts)

    def build_limit(self) -> str:
        if self._limit_val is None:
            return ""
        sql = f"LIMIT {self._limit_val}"
        if self._offset_val is not None:
            sql += f" OFFSET {self._offset_val}"
        return sql


class UpdateWrapper:
    """更新条件构造器

    Usage:
        uw().set("name", "Bob").eq("id", 1)
    """

    def __init__(self):
        self._sets = []
        self._conditions = []

    def set(self, col, val):
        self._sets.append((col, val))
        return self

    def eq(self, col, val):
        self._conditions.append((col, "=", val))
        return self

    def ne(self, col, val):
        self._conditions.append((col, "!=", val))
        return self

    def gt(self, col, val):
        self._conditions.append((col, ">", val))
        return self

    def ge(self, col, val):
        self._conditions.append((col, ">=", val))
        return self

    def lt(self, col, val):
        self._conditions.append((col, "<", val))
        return self

    def le(self, col, val):
        self._conditions.append((col, "<=", val))
        return self

    def build_set(self) -> tuple[str, list]:
        if not self._sets:
            return "", []
        for col, _ in self._sets:
            validate_identifier(col)
        parts = [f"{col} = ?" for col, _ in self._sets]
        params = [val for _, val in self._sets]
        return "SET " + ", ".join(parts), params

    def build_where(self) -> tuple[str, list]:
        if not self._conditions:
            return "", []
        parts = []
        params = []
        for col, op, val in self._conditions:
            validate_identifier(col)
            parts.append(f"{col} {op} ?")
            params.append(val)
        return "WHERE " + " AND ".join(parts), params


def qw() -> QueryWrapper:
    return QueryWrapper()


def uw() -> UpdateWrapper:
    return UpdateWrapper()
