from datetime import date, datetime
from decimal import Decimal

from asyncpg.exceptions import QueryCanceledError
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import create_async_engine
import sqlglot
import sqlglot.expressions as exp

from config import settings


class SQLExecutor:
    def __init__(self, db_url: str = settings.GAME_DATABASE_URL):
        self.engine = create_async_engine(db_url, isolation_level="AUTOCOMMIT")
        self.transaction_engine = create_async_engine(db_url) # For simulating updates

    async def execute_sql(self, sql_query: str, allow_star: bool = False) -> dict:
        sql_query = sql_query.rstrip(";").strip()
        self._validate_sql(sql_query, allow_star=allow_star)
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SET statement_timeout TO 5000"))
                result = await conn.execute(text(sql_query))
                if result.returns_rows:
                    columns = list(result.keys())
                    data = []
                    for row in result.fetchall():
                        processed_row = []
                        for value in row:
                            if isinstance(value, (date, datetime)):
                                processed_row.append(value.isoformat())
                            elif isinstance(value, Decimal):
                                processed_row.append(float(value))
                            else:
                                processed_row.append(value)
                        data.append(processed_row)
                    return {"columns": columns, "data": data, "row_count": len(data)}
                return {"columns": [], "data": [], "row_count": result.rowcount}
        except QueryCanceledError:
            raise HTTPException(
                status_code=400, detail="Время выполнения запроса превышено"
            )
        except StatementError as e:
            raise HTTPException(
                status_code=400, detail=f"Ошибка выполнения: {str(e.orig)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Непредвиденная ошибка базы данных: {str(e)}"
            )

    async def simulate_update(self, sql_query: str, allowed_tables: list[str] = None) -> int:
        """Безопасное выполнение UPDATE с помощью транзакции и отката"""
        sql_query = sql_query.rstrip(";").strip()
        self._validate_sql(sql_query, allow_update=True, allowed_tables=allowed_tables)
        try:
            async with self.transaction_engine.begin() as conn:
                await conn.execute(text("SET statement_timeout TO 5000"))
                result = await conn.execute(text(sql_query))
                rowcount = result.rowcount
                await conn.rollback()
                return rowcount
        except QueryCanceledError:
            raise HTTPException(
                status_code=400, detail="Время выполнения запроса превышено"
            )
        except StatementError as e:
            raise HTTPException(
                status_code=400, detail=f"Ошибка выполнения: {str(e.orig)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Непредвиденная ошибка базы данных: {str(e)}"
            )

    def _validate_sql(self, sql_query: str, allow_update: bool = False, allowed_tables: list[str] = None, allow_star: bool = False):
        """AST проверка SQL-запроса на безопасность"""
        try:
            parsed = sqlglot.parse_one(sql_query, read="postgres")
        except sqlglot.errors.ParseError as e:
            raise HTTPException(status_code=400, detail=f"Ошибка синтаксиса: {str(e)}")

        if not parsed:
            raise HTTPException(status_code=400, detail="Пустой запрос")

        allowed_keys = ["select", "with", "except", "union", "intersect"]
        if allow_update:
            allowed_keys.append("update")

        if parsed.key not in allowed_keys:
            raise HTTPException(status_code=400, detail=f"Запрещенная операция: {parsed.key.upper()}")

        if not allow_star:
            for node in parsed.find_all(exp.Star):
                raise HTTPException(status_code=400, detail="Использование SELECT * запрещено при финальной отправке, перечислите столбцы явно")
            
        for table in parsed.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name.startswith("pg_") or table_name == "user" or table_name == "users" or table_name.startswith("information_schema"):
                raise HTTPException(status_code=400, detail=f"Доступ к системной или запрещенной таблице ({table.name}) запрещен")
            
            if allow_update and allowed_tables and parsed.key == "update":
                if table_name not in [t.lower() for t in allowed_tables]:
                    raise HTTPException(status_code=400, detail=f"Обновление таблицы {table.name} не разрешено в этой задаче")
