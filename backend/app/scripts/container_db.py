"""Explicit container schema management; never invoked by API workers."""

import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = "20261127_rent_confirmation"
LOCK_ID = 743920610


def alembic_config():
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bootstrap", "upgrade", "check", "health"))
    args = parser.parse_args()
    config = alembic_config()
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            if args.action in ("bootstrap", "upgrade"):
                if not connection.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}).scalar():
                    raise RuntimeError("Another schema command is running; retry when it finishes.")
                connection.commit()
            if args.action == "bootstrap":
                count = connection.execute(text("""
                    SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')
                      AND NOT EXISTS (SELECT 1 FROM pg_depend d
                          WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype='e')
                """)).scalar_one()
                if count:
                    raise RuntimeError("Bootstrap requires an empty public schema; existing database left unchanged.")
                sql = (ROOT / "docker" / "base-schema.sql").read_text(encoding="utf-8")
                connection.connection.driver_connection.execute(sql, prepare=False)
                connection.execute(text("INSERT INTO public.alembic_version VALUES (:revision)"), {"revision": BASE_REVISION})
                connection.commit()
                print(f"Base schema installed at {BASE_REVISION}; now run upgrade.")
            elif args.action == "upgrade":
                if not inspect(connection).has_table("users") or not inspect(connection).has_table("alembic_version"):
                    raise RuntimeError("Base schema/version missing. Bootstrap an empty database first; do not stamp an unknown existing schema.")
                if not connection.execute(text("SELECT version_num FROM alembic_version")).first():
                    raise RuntimeError("No recorded revision; reconcile the existing schema before migrating.")
                command.upgrade(config, "head")
                print("Migrations complete.")
            else:
                revisions = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
                if revisions != set(ScriptDirectory.from_config(config).get_heads()):
                    raise RuntimeError("Schema is behind the application; run the explicit migration command.")
                if args.action == "health":
                    with urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
                        if json.load(response).get("db") != 1:
                            raise RuntimeError("API database check failed.")
                print("Database ready at migration head.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
