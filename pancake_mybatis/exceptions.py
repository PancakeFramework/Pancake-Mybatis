"""MyBatis 自定义异常"""


class MyBatisError(Exception):
    """MyBatis 基础异常"""
    pass


class SqlParseError(MyBatisError):
    """SQL 解析错误"""
    pass


class TransactionError(MyBatisError):
    """事务错误"""
    pass


class MapperError(MyBatisError):
    """Mapper 注册/使用错误"""
    pass


class DatabaseError(MyBatisError):
    """数据库连接/操作错误"""
    pass


class PageError(MyBatisError):
    """分页参数错误"""
    pass
