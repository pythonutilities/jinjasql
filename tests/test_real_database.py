import os
import unittest

from jinjasql import JinjaSql

try:
    import sqlalchemy
    from testcontainers.postgres import PostgresContainer
    from testcontainers.mysql import MySqlContainer
    HAVE_TEST_DEPS = True
except ImportError:
    HAVE_TEST_DEPS = False


def _docker_available():
    if not HAVE_TEST_DEPS:
        return False
    try:
        import docker
        docker.from_env().ping()
        return True
    except Exception:
        return False


requires_docker = unittest.skipUnless(
    _docker_available(),
    "requires testcontainers, sqlalchemy and a running Docker daemon",
)


@requires_docker
class PostgresTest(unittest.TestCase):

    def setUp(self):
        self.container = PostgresContainer("postgres:15.3")
        if os.name == "nt":
            self.container.get_container_host_ip = lambda: "localhost"
        self.container.start()
        self.addCleanup(self.container.stop)
        self.engine = sqlalchemy.create_engine(self.container.get_connection_url())

    def test_bind_array(self):
        'It should be possible to bind arrays in a query'
        j = JinjaSql(param_style='named')
        data = {
            "some_num": 1,
            "some_array": [1,2,3]
        }
        template = """
            SELECT {{some_num}} = ANY({{some_array}})
        """
        query, params = j.prepare_query(template, data)
        with self.engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(query), params).fetchone()
        self.assertTrue(result[0])

    def test_quoted_tables(self):
        j = JinjaSql()
        data = {
            "all_tables": ("information_schema", "tables")
        }
        template = """
            select table_name from {{all_tables|identifier}}
            where table_name = 'pg_user'
        """
        query, params = j.prepare_query(template, data)
        with self.engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(query), params).fetchall()
        self.assertEqual(len(result), 1)


@requires_docker
class MySqlTest(unittest.TestCase):

    def setUp(self):
        self.container = (
            MySqlContainer("mysql/mysql-server", platform="linux/amd64")
            .with_exposed_ports(3306)
            .with_env("MYSQL_USER", "root")
            .with_env("MYSQL_PASSWORD", "test")
            .with_env("MYSQL_DATABASE", "test")
        )
        if os.name == "nt":
            self.container.get_container_host_ip = lambda: "localhost"
        self.container.start()
        self.addCleanup(self.container.stop)
        url = self.container.get_connection_url()
        if url.startswith("mysql://"):
            url = url.replace("mysql://", "mysql+pymysql://", 1)
        self.engine = sqlalchemy.create_engine(url)

    def test_quoted_tables(self):
        j = JinjaSql(identifier_quote_character='`')
        data = {
            "database": "information_schema",
            "table_name" : "TABLES"
        }
        template = """
            select * from {{database|identifier}}.{{table_name|identifier}};
        """
        query, params = j.prepare_query(template, data)
        with self.engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(query), params).fetchall()
        self.assertTrue(len(result)>1)


if __name__ == '__main__':
    unittest.main()
