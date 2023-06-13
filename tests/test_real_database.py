import os
from testcontainers.postgres import PostgresContainer
from testcontainers.mysql import MySqlContainer
import sqlalchemy
import unittest
from jinjasql import JinjaSql

class PostgresTest(unittest.TestCase):

    # Core idea inspired from 
    # https://stackoverflow.com/questions/8416208/in-python-is-there-a-good-idiom-for-using-context-managers-in-setup-teardown
    # 
    # Override the run method to automatically
    # a. launch a postgres docker container
    # b. create a sqlalchemy connection 
    # c. at the end of the test, kill the docker container
    def run(self, result=None):
        self.postgresql_test_container = PostgresContainer("postgres:15.3")
        if os.name == "nt":
            self.postgresql_test_container.get_container_host_ip = lambda: "localhost"
        self.postgresql_test_container.start()
        self.engine = sqlalchemy.create_engine(self.postgresql_test_container.get_connection_url(),echo=True)
        super(PostgresTest, self).run(result)

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

class MySqlTest(unittest.TestCase):
    def run(self, result=None):
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
        self.engine = sqlalchemy.create_engine(self.container.get_connection_url())
        super(MySqlTest, self).run(result)

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