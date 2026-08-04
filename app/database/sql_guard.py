from dataclasses import dataclass

import sqlglot
from sqlglot import exp


ALLOWED_TABLES = {"users", "orders", "test_runs", "agent_traces"}
DANGEROUS_FUNCTIONS = {"load_file", "sleep", "benchmark", "sys_exec", "pg_read_file"}


class UnsafeSqlError(ValueError):
    pass


@dataclass(frozen=True)
class GuardedSql:
    sql: str
    tables: tuple[str, ...]


def guard_readonly_sql(sql: str, max_rows: int = 100, dialect: str = "mysql") -> GuardedSql:
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as exc:
        raise UnsafeSqlError(f"invalid SQL: {exc}") from exc
    if len(statements) != 1 or statements[0] is None:
        raise UnsafeSqlError("exactly one SQL statement is required")
    tree = statements[0]
    if tree.key.lower() not in {"select", "show", "describe", "explain"}:
        raise UnsafeSqlError("only SELECT/SHOW/DESCRIBE/EXPLAIN are allowed")
    forbidden_nodes = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Command)
    if any(tree.find(node) is not None for node in forbidden_nodes):
        raise UnsafeSqlError("write or command statements are forbidden")
    functions = {
        (getattr(f, "name", "") or f.sql_name()).lower()
        for f in tree.find_all(exp.Func)
    }
    if functions & DANGEROUS_FUNCTIONS:
        raise UnsafeSqlError("dangerous SQL function is forbidden")
    tables = tuple(sorted({table.name.lower() for table in tree.find_all(exp.Table)}))
    unknown = set(tables) - ALLOWED_TABLES
    if unknown:
        raise UnsafeSqlError(f"table is not allowlisted: {sorted(unknown)}")
    if isinstance(tree, exp.Select):
        limit = tree.args.get("limit")
        if limit is None:
            tree = tree.limit(max_rows)
        else:
            value = limit.expression
            if not isinstance(value, exp.Literal) or not value.is_int:
                raise UnsafeSqlError("LIMIT must be an integer literal")
            if int(value.this) > max_rows:
                tree.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return GuardedSql(sql=tree.sql(dialect=dialect), tables=tables)
