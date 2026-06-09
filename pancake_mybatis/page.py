"""分页支持 — Page 对象"""

from dataclasses import dataclass, field


@dataclass
class Page:
    """分页对象

    用法:
        page = Page(current=1, size=20)
        result = await mapper.select_page(page, qw().eq("status", 1))
        # result.records — 数据列表
        # result.total   — 总条数
        # result.pages   — 总页数
    """
    current: int = 1
    size: int = 20
    total: int = 0
    records: list = field(default_factory=list)

    def __post_init__(self):
        if self.current < 1:
            self.current = 1
        if self.size < 1:
            self.size = 20

    @property
    def offset(self) -> int:
        return (self.current - 1) * self.size

    @property
    def pages(self) -> int:
        if self.total <= 0:
            return 0
        return (self.total + self.size - 1) // self.size

    @property
    def has_next(self) -> bool:
        return self.current < self.pages

    @property
    def has_prev(self) -> bool:
        return self.current > 1

    def to_dict(self) -> dict:
        return {
            "current": self.current,
            "size": self.size,
            "total": self.total,
            "pages": self.pages,
            "records": self.records,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }
