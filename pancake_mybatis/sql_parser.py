"""SQL 解析器 — #{param} 参数绑定和动态 SQL"""

import re
import logging

logger = logging.getLogger(__name__)

# 合法 SQL 标识符：字母/下划线开头，后跟字母/数字/下划线
_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def validate_identifier(name: str) -> str:
    """校验 SQL 标识符（表名、列名），防注入

    只允许: 字母、数字、下划线，且必须以字母或下划线开头。
    支持 "schema.table" 格式（按 . 拆分后逐段校验）。

    Args:
        name: 表名或列名

    Returns:
        校验通过的原名称

    Raises:
        ValueError: 标识符不合法
    """
    if not name:
        raise ValueError("SQL 标识符不能为空")
    for part in name.split("."):
        if not _IDENTIFIER_RE.match(part):
            raise ValueError(
                f"非法 SQL 标识符: '{name}' — "
                f"只允许字母、数字、下划线，且以字母或下划线开头"
            )
    return name


def parse_sql(sql: str, params: dict) -> tuple[str, list]:
    """将 #{name} 替换为 ? 占位符

    Args:
        sql: "SELECT * FROM users WHERE name = #{name}"
        params: {"name": "Alice"}

    Returns:
        ("SELECT * FROM users WHERE name = ?", ["Alice"])
    """
    values = []

    def replacer(match):
        key = match.group(1).strip()
        values.append(params.get(key))
        return "?"

    parsed = re.sub(r"#\{(\w+)\}", replacer, sql)
    return parsed, values


def parse_dynamic_sql(sql: str, params: dict) -> str:
    """解析动态 SQL: <if>, <where>, <choose>/<when>/<otherwise>"""
    # 1. <if test="...">
    def replace_if(match):
        condition = match.group(1).strip()
        body = match.group(2)
        return body if params.get(condition) else ""

    sql = re.sub(r'<if\s+test="([^"]+)">(.*?)</if>', replace_if, sql, flags=re.DOTALL)

    # 2. <choose>/<when>/<otherwise>
    def replace_choose(match):
        body = match.group(1)
        # 提取所有 <when>
        when_pattern = re.compile(r'<when\s+test="([^"]+)">(.*?)</when>', re.DOTALL)
        for when_match in when_pattern.finditer(body):
            condition = when_match.group(1).strip()
            when_body = when_match.group(2)
            if params.get(condition):
                return when_body
        # 没有匹配的 when，用 <otherwise>
        otherwise_match = re.search(r"<otherwise>(.*?)</otherwise>", body, re.DOTALL)
        if otherwise_match:
            return otherwise_match.group(1)
        return ""

    sql = re.sub(r"<choose>(.*?)</choose>", replace_choose, sql, flags=re.DOTALL)

    # 3. <where>
    def replace_where(match):
        body = match.group(1).strip()
        if not body:
            return ""
        body = re.sub(r"^\s*AND\s+", "", body, flags=re.IGNORECASE)
        body = re.sub(r"^\s*OR\s+", "", body, flags=re.IGNORECASE)
        return "WHERE " + body

    sql = re.sub(r"<where>(.*?)</where>", replace_where, sql, flags=re.DOTALL)

    # 4. <set> (UPDATE SET 去掉尾部逗号)
    def replace_set(match):
        body = match.group(1).strip()
        if not body:
            return ""
        body = re.sub(r",\s*$", "", body)
        return "SET " + body

    sql = re.sub(r"<set>(.*?)</set>", replace_set, sql, flags=re.DOTALL)

    return sql.strip()


def convert_placeholders(sql: str, style: str = "q") -> str:
    """转换占位符风格

    Args:
        sql: 含 ? 占位符的 SQL
        style: "q" → ?, "pg" → $1,$2,...

    Returns:
        转换后的 SQL
    """
    if style == "q":
        return sql
    counter = [0]
    def replacer(_):
        counter[0] += 1
        return f"${counter[0]}"
    return re.sub(r"\?", replacer, sql)
