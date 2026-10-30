import re

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify_skill(name: str) -> str:
    """Normalize a skill name to its tag: 'Active Directory' and 'active-directory' match."""
    return _NON_SLUG.sub("-", name.strip().lower()).strip("-")


def normalize_skills(names: list[str]) -> set[str]:
    return {slug for slug in (slugify_skill(name) for name in names) if slug}
