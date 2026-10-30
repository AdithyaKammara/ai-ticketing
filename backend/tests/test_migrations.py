import asyncio

from alembic import command

from tests.conftest import TEST_DATABASE_URL, alembic_config, recreate_database

MIGRATIONS_DB = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/ticketing_migrations_test"


def test_migrations_upgrade_and_downgrade_on_empty_database() -> None:
    asyncio.run(recreate_database(MIGRATIONS_DB))
    config = alembic_config(MIGRATIONS_DB)

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)  # models and migrations agree
