#!/usr/bin/env python3

# mock redcap reports
# from unittest import mock
import unittest

import sys
from os import path
from pathlib import Path
from unittest.mock import patch
from csv_diff import load_csv, compare

path_root = Path(__file__).parents[1]
sys.path.append(str(path_root))

# pylint: disable=import-error, wrong-import-position
import orders.delivery_express_order as de
import orders.utils.redcap as redcap_utils
from etc.ordering_script_config_map import PROJECT_DICT


class TestDEOrderGeneration(unittest.TestCase):

    # @unittest.skip('skip')
    def test_redcap_connection(self):
        # boolean statement if get_redcap_orders() throws no errors
        # later on loop through each project classification
        for project in PROJECT_DICT:
            with self.subTest(project=project):
                try:
                    redcap_project = redcap_utils.init_project(project)
                    redcap_utils.get_redcap_orders(redcap_project, project)
                # pylint: disable=broad-except
                except BaseException as error:
                    self.fail(f"get_redcap_orders failed with {error}")

    def test_order_gen(self):
        for project in PROJECT_DICT:  #(p for p in PROJECT_DICT if p == 'AIRS'):
            with self.subTest(project=project):
                redcap_project = redcap_utils.init_project(project)
                proj_name = project.replace(" ", "_").lower()

                mock_csv = path.join(
                    path_root,
                    f'tests/data/{proj_name}/{proj_name}_mock_report.csv')
                redcap_report = open(mock_csv, 'r', encoding='utf8')
                with patch('orders.delivery_express_order.Project._call_api',
                           return_value=(redcap_report.read(), '')):
                    actual_orders = redcap_utils.get_redcap_orders(
                        redcap_project, project)
                redcap_report.close()

                actual_orders = de.format_orders(actual_orders, project)
                generated_csv = path.join(
                    path_root,
                    f'tests/data/{proj_name}/{proj_name}_gen_order.csv')
                actual_orders.to_csv(generated_csv, index=False)

                expected_csv = path.join(
                    path_root,
                    f'tests/data/{proj_name}/{proj_name}_expected_order.csv')
                # expected: one csv of expected correct orders (static)
                # generated: what our ordering script returns (generated when we run the test)
                expected = open(expected_csv, encoding='utf-8')
                generated = open(generated_csv, encoding='utf-8')
                diff = compare(load_csv(expected), load_csv(generated))
                expected.close()
                generated.close()

                for _, value in diff.items():
                    if value:
                        raise self.fail(
                            f'Order was not generated as expected: {diff}')


if __name__ == '__main__':
    unittest.main()
