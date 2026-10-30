from app.db.enums import Category, Severity
from app.schemas.common import DepartmentOut, Schema


class CategoryOut(Schema):
    category: Category
    department: DepartmentOut
    default_skills: list[str]
    auto_resolve_allowed: bool
    severity_floor: Severity | None
