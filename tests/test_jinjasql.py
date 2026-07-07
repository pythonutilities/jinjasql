import sqlite3
import unittest
from jinja2 import DictLoader
from jinja2 import Environment
from jinjasql import JinjaSql
from datetime import date
from yaml import safe_load_all
from os.path import dirname, abspath, join


YAML_TESTS_ROOT = join(dirname(abspath(__file__)), "yaml")

_DATA = {
    "etc": {
        "columns": "project, timesheet, hours",
        "lt": "<",
        "gt": ">",
    },
    "ids": {
        "field1": "id",
        "field2": "name",
        "table": ("public", "users"),
    },
    "malicious": {
        "table": "users; drop table users; --",
        "field": "id\" FROM users; drop table users; --"
    },
    "request": {
        "project": {
            "id": 123,
            "name": "Acme Project"
        },
        "project_id": 123,
        "days": ["mon", "tue", "wed", "thu", "fri"],
        "day": "mon",
        "start_date": date.today(),
    },
    "session": {
        "user_id": u"sripathi"
    }
}

class JinjaSqlTest(unittest.TestCase):
    def setUp(self):
        self.j = JinjaSql(param_style="format")

    def test_import(self):
        utils = """
        {% macro print_where(value) -%}
        WHERE dummy_col = {{value}}
        {%- endmacro %}
        """
        source = """
        {% import 'utils.sql' as utils %}
        select * from dual {{ utils.print_where(100) }}
        """
        loader = DictLoader({"utils.sql" : utils})
        env = Environment(loader=loader)

        j = JinjaSql(env,param_style="format")
        query, bind_params = j.prepare_query(source, _DATA)
        expected_query = "select * from dual WHERE dummy_col = %s"
        self.assertEqual(query.strip(), expected_query.strip())
        self.assertEqual(len(bind_params), 1)
        self.assertEqual(list(bind_params)[0], 100)

    def test_include(self):
        where_clause = """where project_id = {{request.project_id}}"""
        
        source = """
        select * from dummy {% include 'where_clause.sql' %}
        """
        loader = DictLoader({"where_clause.sql" : where_clause})
        env = Environment(loader=loader)

        j = JinjaSql(env,param_style="format")
        query, bind_params = j.prepare_query(source, _DATA)
        expected_query = "select * from dummy where project_id = %s"
        self.assertEqual(query.strip(), expected_query.strip())
        self.assertEqual(len(bind_params), 1)
        self.assertEqual(list(bind_params)[0], 123)

    def test_precompiled_template(self):
        source = "select * from dummy where project_id = {{ request.project_id }}"
        j = JinjaSql(param_style="format")
        query, bind_params = j.prepare_query(j.env.from_string(source), _DATA)
        expected_query = "select * from dummy where project_id = %s"
        self.assertEqual(query.strip(), expected_query.strip())

    def test_large_inclause(self):
        num_of_params = 50000
        alphabets = ['A'] * num_of_params
        source = "SELECT 'x' WHERE 'A' in {{alphabets | inclause}}"
        j = JinjaSql(param_style="format")
        query, bind_params = j.prepare_query(source, {"alphabets": alphabets})
        self.assertEqual(len(bind_params), num_of_params)
        self.assertEqual(query, "SELECT 'x' WHERE 'A' in (" + "%s," * (num_of_params - 1) + "%s)")

    def test_large_likeclause(self):
        source = "SELECT 'x' WHERE project_id ilike {{('%%'~request.project_id~'%%')}}"
        j = JinjaSql(param_style="named")
        query, bind_params = j.prepare_query(source, _DATA)
        self.assertEqual(len(bind_params), 1)
        self.assertEqual(query, "SELECT 'x' WHERE project_id ilike :bind0_1")

    def test_identifier_filter(self):
        j = JinjaSql(param_style="format")
        template = 'select * from {{table_name | identifier}}'
        
        tests = [
            ('users', 'select * from "users"'),
            (('myschema', 'users'), 'select * from "myschema"."users"'),
            ('a"b', 'select * from "a""b"'),
            (('users',), 'select * from "users"'),
        ]
        for test in tests:
            query, _ = j.prepare_query(template, {'table_name': test[0]})
            self.assertEqual(query, test[1])


    def test_list_as_first_dynamic_parameter(self):
        # Regression test for
        # https://github.com/pythonutilities/jinjasql/issues/13
        query, bind_params = self.j.prepare_query(
            "select * from t where a in {{ ids | inclause }} and b = {{ x }}",
            {"ids": [1, 2, 3], "x": 9})
        self.assertEqual(query, "select * from t where a in (%s,%s,%s) and b = %s")
        self.assertEqual(list(bind_params), [1, 2, 3, 9])

    def test_nested_reference_generates_valid_named_param(self):
        # Dots in auto-generated bind names are invalid in named style
        # (sqlite/Oracle): {{ request.project_id }} must not produce
        # the placeholder ":request.project_id_1"
        j = JinjaSql(param_style="named")
        query, bind_params = j.prepare_query(
            "select * from t where project_id = {{ request.project_id }}", _DATA)
        self.assertEqual(query, "select * from t where project_id = :request_project_id_1")
        self.assertEqual(bind_params, {"request_project_id_1": 123})

    def test_named_params_execute_on_sqlite(self):
        j = JinjaSql(param_style="named")
        query, bind_params = j.prepare_query(
            "select {{ request.project_id }} where 1 in {{ request.days_count | inclause }}",
            {"request": {"project_id": 123, "days_count": [1, 2]}})
        conn = sqlite3.connect(":memory:")
        try:
            self.assertEqual(conn.execute(query, bind_params).fetchall(), [(123,)])
        finally:
            conn.close()

    def test_invalid_param_style_rejected(self):
        with self.assertRaises(ValueError):
            JinjaSql(param_style="fromat")

    def test_variable_named_like_filter_is_bound(self):
        # A variable that merely shares a name with one of our filters
        # must still be bound, not rendered raw
        query, bind_params = self.j.prepare_query(
            "select * from dual where x = {{ sqlsafe }}",
            {"sqlsafe": "1; drop table users; --"})
        self.assertEqual(query, "select * from dual where x = %s")
        self.assertEqual(list(bind_params), ["1; drop table users; --"])

    def test_manual_bind_filter(self):
        query, bind_params = self.j.prepare_query(
            "select * from user where id = {{ userid | bind }}",
            {"userid": 143})
        self.assertEqual(query, "select * from user where id = %s")
        self.assertEqual(list(bind_params), [143])

    def test_empty_inclause_raises(self):
        with self.assertRaises(ValueError):
            self.j.prepare_query(
                "select 'x' where day in {{ days | inclause }}",
                {"days": []})

    def test_string_inclause_raises(self):
        with self.assertRaises(ValueError):
            self.j.prepare_query(
                "select 'x' where day in {{ day | inclause }}",
                {"day": "mon"})

    def test_identifier_filter_rejects_bad_input(self):
        for bad_identifier in (123, ("users", 123), "a\x00b"):
            with self.assertRaises(ValueError):
                self.j.prepare_query(
                    "select * from {{ table_name | identifier }}",
                    {"table_name": bad_identifier})

    def test_identifier_filter_backtick(self):
        j = JinjaSql(identifier_quote_character='`')
        template = 'select * from {{table_name | identifier}}'
        
        tests = [
            ('users', 'select * from `users`'),
            (('myschema', 'users'), 'select * from `myschema`.`users`'),
            ('a`b', 'select * from `a``b`'),
        ]
        for test in tests:
            query, _ = j.prepare_query(template, {'table_name': test[0]})
            self.assertEqual(query, test[1])

def generate_yaml_tests():
    file_path = join(YAML_TESTS_ROOT, "macros.yaml")
    with open(file_path) as f:
        configs = safe_load_all(f)
        for config in configs:
            yield (config['name'], _generate_test(config))

def _generate_test(config):
    def yaml_test(self):
        source = config['template']
        for (param_style, expected_sql) in config['expected_sql'].items():
            jinja = JinjaSql(param_style=param_style)
            query, bind_params = jinja.prepare_query(source, _DATA)

            if 'expected_params' in config:
                if param_style in ('pyformat', 'named'):
                    self.assertEqual(bind_params, config['expected_params']['as_dict'])
                else:
                    self.assertEqual(list(bind_params), config['expected_params']['as_list'])

            self.assertEqual(query.strip(), expected_sql.strip())

    return yaml_test

for test in generate_yaml_tests():
    test_name = test[0]
    test_function = test[1]
    setattr(JinjaSqlTest, test_name, test_function)

if __name__ == '__main__':
    unittest.main()
