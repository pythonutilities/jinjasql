import unittest

from tests.test_jinjasql import JinjaSqlTest
from tests.test_real_database import PostgresTest, MySqlTest


def all_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for test_case in (JinjaSqlTest, PostgresTest, MySqlTest):
        suite.addTests(loader.loadTestsFromTestCase(test_case))
    return suite
