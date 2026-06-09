# Pancake MyBatis Plus

Pancake 框架的 MyBatis Plus ORM 插件，提供异步数据库操作。

## Features

- **@Mapper 注解** — 标记 Mapper 类，自动注册到 IoC 容器
- **BaseMapper** — 内置 CRUD 方法（select_by_id, insert, update_by_id, delete_by_id 等）
- **SQL 注解** — @Select, @Insert, @Update, @Delete 自定义 SQL
- **链式查询** — QueryWrapper / UpdateWrapper 构造条件
- **动态 SQL** — `<if>`, `<where>`, `<choose>` 标签支持

## Quick Start

```python
from dataclasses import dataclass

@Mapper
class UserMapper(BaseMapper):
    @dataclass
    class User:
        id: int = None
        name: str = None
        age: int = None

    _entity_class = User
    _table_name = "users"

    @Select("SELECT * FROM users WHERE name = #{name}")
    async def find_by_name(self, name: str) -> list[User]: ...
```

## Configuration

```yaml
mybatis:
  database:
    url: resource/db/app.db
```

## License

MIT
