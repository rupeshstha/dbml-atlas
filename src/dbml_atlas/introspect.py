"""dbml-atlas introspect — read a live database and emit DBML to stdout.

Supported backends (all optional):
  sqlite3   stdlib — always available
  psycopg2  pip install dbml-atlas[postgres]
  pymysql   pip install dbml-atlas[mysql]

Usage:
  dbml-atlas introspect sqlite:///path/to/file.db
  dbml-atlas introspect postgresql://user:pass@host/db
  dbml-atlas introspect mysql://user:pass@host/db
"""
from __future__ import annotations

import re
import sys


def _connect(dsn: str):
    """Return (connection, dialect) or exit with a helpful message."""
    if dsn.startswith("sqlite:///"):
        import sqlite3
        path = dsn[len("sqlite:///"):]
        return sqlite3.connect(path), "sqlite"
    if dsn.startswith("postgresql://") or dsn.startswith("postgres://"):
        try:
            import psycopg2  # type: ignore
        except ImportError:
            sys.exit("psycopg2 not installed. Run: pip install dbml-atlas[postgres]")
        return psycopg2.connect(dsn), "postgres"
    if dsn.startswith("mysql://"):
        try:
            import pymysql  # type: ignore
        except ImportError:
            sys.exit("pymysql not installed. Run: pip install dbml-atlas[mysql]")
        url = dsn[len("mysql://"):]
        m = re.match(r"(?:([^:@]+)(?::([^@]*))?@)?([^:/]+)(?::(\d+))?/(.+)", url)
        if not m:
            sys.exit(f"Cannot parse MySQL DSN: {dsn}")
        user, pw, host, port, db = m.groups()
        return pymysql.connect(host=host, user=user, password=pw or "", database=db,
                               port=int(port or 3306)), "mysql"
    sys.exit("Unsupported DSN scheme. Use sqlite:///, postgresql://, or mysql://")


def _columns_sqlite(cur, table: str) -> list[dict]:
    cur.execute(f"PRAGMA table_info({table})")
    cols = []
    for row in cur.fetchall():
        cols.append(dict(
            name=row[1], type=row[2] or "text",
            pk=bool(row[5]), not_null=bool(row[3]),
            default=str(row[4]) if row[4] is not None else None,
        ))
    return cols


def _columns_postgres(cur, table: str) -> list[dict]:
    cur.execute("""
        SELECT c.column_name, c.data_type, c.is_nullable, c.column_default,
               CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.column_name FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
              ON tc.constraint_name=ku.constraint_name AND tc.table_name=ku.table_name
            WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_name=%s
        ) pk ON c.column_name=pk.column_name
        WHERE c.table_name=%s AND c.table_schema='public'
        ORDER BY c.ordinal_position
    """, (table, table))
    return [dict(name=r[0], type=r[1], not_null=r[2] == "NO",
                 default=r[3], pk=bool(r[4])) for r in cur.fetchall()]


def _columns_mysql(cur, table: str, db: str) -> list[dict]:
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
        ORDER BY ORDINAL_POSITION
    """, (db, table))
    return [dict(name=r[0], type=r[1], not_null=r[2] == "NO",
                 default=r[3], pk=r[4] == "PRI") for r in cur.fetchall()]


def _fks_sqlite(cur, table: str) -> list[dict]:
    cur.execute(f"PRAGMA foreign_key_list({table})")
    return [dict(from_col=r[3], to_table=r[2], to_col=r[4]) for r in cur.fetchall()]


def _fks_postgres(cur, table: str) -> list[dict]:
    cur.execute("""
        SELECT kcu.column_name, ccu.table_name, ccu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name=tc.constraint_name AND ccu.table_schema=tc.table_schema
        WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_name=%s AND tc.table_schema='public'
    """, (table,))
    return [dict(from_col=r[0], to_table=r[1], to_col=r[2]) for r in cur.fetchall()]


def _fks_mysql(cur, table: str, db: str) -> list[dict]:
    cur.execute("""
        SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL
    """, (db, table))
    return [dict(from_col=r[0], to_table=r[1], to_col=r[2]) for r in cur.fetchall()]


def introspect(dsn: str) -> str:
    """Connect to a database and return DBML text."""
    conn, dialect = _connect(dsn)
    cur = conn.cursor()

    if dialect == "sqlite":
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
    elif dialect == "postgres":
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        tables = [r[0] for r in cur.fetchall()]
    else:  # mysql
        db = dsn.rsplit("/", 1)[-1]
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name", (db,))
        tables = [r[0] for r in cur.fetchall()]

    lines = [f"// Generated by dbml-atlas introspect from {dsn.split('@')[-1]}", ""]

    for table in tables:
        if dialect == "sqlite":
            cols = _columns_sqlite(cur, table)
            fks = _fks_sqlite(cur, table)
        elif dialect == "postgres":
            cols = _columns_postgres(cur, table)
            fks = _fks_postgres(cur, table)
        else:
            db = dsn.rsplit("/", 1)[-1]
            cols = _columns_mysql(cur, table, db)
            fks = _fks_mysql(cur, table, db)

        fk_cols = {f["from_col"] for f in fks}
        lines.append(f"Table {table} {{")
        for c in cols:
            settings = []
            if c["pk"]:
                settings.append("pk")
            if c["not_null"] and not c["pk"]:
                settings.append("not null")
            if c["default"] is not None:
                dv = c["default"]
                settings.append(f"default: `{dv}`" if re.search(r"[()']", dv) else f"default: {dv!r}")
            if c["name"] in fk_cols:
                fk = next(f for f in fks if f["from_col"] == c["name"])
                settings.append(f"ref: > {fk['to_table']}.{fk['to_col']}")
            bracket = f" [{', '.join(settings)}]" if settings else ""
            lines.append(f"  {c['name']}  {c['type']}{bracket}")
        lines.append("}")
        lines.append("")

    conn.close()
    return "\n".join(lines)
