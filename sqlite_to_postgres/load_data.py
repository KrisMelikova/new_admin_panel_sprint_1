import os
import sqlite3
from dataclasses import astuple, fields

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as pg_connection
from psycopg2.extras import DictCursor

from dataclasses_sqlite_to_pg import Genre, GenreMovie, Movie, Person, PersonMovie
from sqlite_to_postgres.utils import sqlite_conn_context, sqlite_curs_context

load_dotenv()

dataclass_query_mapping = {
    Movie: "SELECT title, description, creation_date, type, created_at, updated_at, id, rating FROM film_work;",
    Genre: "SELECT name, description, created_at, updated_at, id from genre;",
    GenreMovie: "SELECT film_work_id, genre_id, created_at, id from genre_film_work;",
    Person: "SELECT full_name, created_at, updated_at, id from person;",
    PersonMovie: "SELECT film_work_id, person_id, role, created_at, id from person_film_work;",
}

dataclass_tables_mapping = {
    Movie: "content.film_work",
    Genre: "content.genre",
    GenreMovie: "content.genre_film_work",
    Person: "content.person",
    PersonMovie: "content.person_film_work",
}


def load_data_from_sqlite(sqlite_conn: sqlite3.Connection, dt, query):
    """ Загрузка данных из SQLite. """

    with sqlite_curs_context(sqlite_conn) as sqlite_cursor:
        try:
            sqlite_cursor.execute(query)
        except sqlite3.Error as sqlite_err:
            raise f"SQLite error while SELECT: {sqlite_err}"

        prepared_dt_data = []
        while True:
            data = sqlite_cursor.fetchmany(100)
            if not data:
                break
            dt_data = [dt(*element) for element in data]
            prepared_dt_data.extend(dt_data)

        return prepared_dt_data


def load_to_postgres(data_from_sqlite, pg_conn, dt):
    """ Загрузка данных в Postgres. """

    column_names = [field.name for field in fields(data_from_sqlite[0])]
    column_names_str = ",".join(column_names)
    col_count = ", ".join(["%s"] * len(column_names))

    with pg_conn.cursor() as pg_cursor:
        bind_values = ",".join(
            pg_cursor.mogrify(f"({col_count})", astuple(item)).decode("utf-8") for item in data_from_sqlite)

        table_name = dataclass_tables_mapping[dt]

        query = f"INSERT INTO {table_name} ({column_names_str}) VALUES {bind_values} ON CONFLICT (id) DO NOTHING"

        try:
            pg_cursor.execute(query)
        except psycopg2.Error as pg_err:
            raise f"PostgreSQL error while INSERT: {pg_err}"


def load_data_from_sqlite_to_postgres(sqlite_conn: sqlite3.Connection, pg_conn: pg_connection):
    """ Основной метод загрузки данных из SQLite в Postgres. """

    for dt, query in dataclass_query_mapping.items():
        data_from_sqlite = load_data_from_sqlite(sqlite_conn, dt, query)

        load_to_postgres(data_from_sqlite, pg_conn, dt)


if __name__ == "__main__":
    PG_DSL = {
        "dbname": os.environ.get("DB_NAME"),
        "user": os.environ.get("DB_USER"),
        "password": os.environ.get("DB_PASSWORD"),
        "host": os.environ.get("DB_HOST"),
        "port": os.environ.get("DB_PORT"),
    }

    SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH")

    with (sqlite_conn_context(SQLITE_DB_PATH) as sqlite_conn,
          psycopg2.connect(**PG_DSL, cursor_factory=DictCursor) as pg_conn):
        load_data_from_sqlite_to_postgres(sqlite_conn, pg_conn)

    pg_conn.close()
