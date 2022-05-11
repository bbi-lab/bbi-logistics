from lib2to3.pytree import Base
import unittest
from unittest.mock import patch
import json
import sys
from os import path
from pathlib import Path

path_root = Path(__file__).parents[1]
sys.path.append(str(path_root))

# pylint: disable=import-error, wrong-import-position
import orders.delivery_express_order as de
import orders.cascadia_return as cr


class TestCascadiaReturn(unittest.TestCase):

    def setUp(self):
        project = 'Cascadia'
        redcap_project = de.init_project(project)

        mock_csv = path.join(path_root,
                             'tests/data/cascadia/cascadia_mock_report.csv')
        redcap_report = open(mock_csv, 'r', encoding='utf8')
        with patch('orders.delivery_express_order.Project._call_api',
                   return_value=(redcap_report.read(), '')):
            redcap_orders = de.get_redcap_orders(redcap_project, project)
        redcap_report.close()

        redcap_orders = de.format_longitudinal(project, redcap_orders)
        redcap_orders['Project Name'] = redcap_orders.apply(
            lambda row: de.assign_project(row, project), axis=1)
        self.redcap_orders = redcap_orders
        print(redcap_orders)

    def test_api_connection(self):
        try:
            self.redcap_orders.apply(cr.get_de_orders, axis=1)
        except BaseException as err:
            self.fail(f'failed api connection test: {err}')

    def test_cascadia_return(self):
        order_num_map = {"10000060": "DE543123", "20002340": "DE565435"}

        class MockResponse:

            def __init__(self, *args, **kwargs):
                print(kwargs.get('data'))
                id = json.loads(kwargs.get('data'))['query']
                self.text = json.dumps({
                    'totalCount':
                    2,
                    'items': [{
                        'orderId': 'DE907535',
                        'createdAt': '2022-03-14T06:54:19.7770043-07:00',
                        'referenceNumber1': '213',
                        'referenceNumber3': 'CASCADIA_PDX'
                    }, {
                        'orderId': order_num_map[f'{int(id)}'],
                        'createdAt': '2022-05-11T06:54:19.7770043-07:00',
                        'referenceNumber1': int(id),
                        'referenceNumber3': 'CASCADIA_SEA'
                    }]
                })

        redcap_orders = self.redcap_orders
        with patch('orders.cascadia_return.requests.post',
                   side_effect=MockResponse):
            redcap_orders['orderId'] = redcap_orders.dropna(
                subset=['Record Id']).apply(cr.get_de_orders, axis=1)

        print(redcap_orders)
        redcap_orders.dropna(subset=['Record Id']).apply(
            lambda x: self.assertEqual(order_num_map[f'{int(x["Record Id"])}'],
                                       x['orderId']),
            axis=1)

        try:
            formatted_import = cr.format_orders_import(redcap_orders)
        except BaseException as err:
            self.fail(f'failed during export formatting: {err}')


if __name__ == '__main__':
    unittest.main()
