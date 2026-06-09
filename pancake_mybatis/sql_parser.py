"""SQL 解析器 — #{param} 参数绑定和动态 SQL"""

import re


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
