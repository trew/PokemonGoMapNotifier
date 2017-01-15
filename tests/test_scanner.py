import unittest
import scanner
import datetime
import time


class TestUtils(unittest.TestCase):
    def test_get_accounts(self):
        scanner.add_account('a', 'a')
        scanner.add_account('b', 'b')
        scanner.add_account('c', 'c')

        now = datetime.datetime.utcnow()
        scanner.accounts[1]['last_scan'] = now - datetime.timedelta(minutes=5)
        scanner.accounts[2]['last_scan'] = now - datetime.timedelta(minutes=2)

        account = scanner.get_account()
        self.assertEqual('a', account['username'])

        now = datetime.datetime.utcnow()
        scanner.accounts[0]['last_scan'] = now - datetime.timedelta(minutes=15)
        scanner.accounts[1]['last_scan'] = now - datetime.timedelta(minutes=5)
        scanner.accounts[2]['last_scan'] = now - datetime.timedelta(minutes=2)

        account = scanner.get_account()
        self.assertEqual('a', account['username'])

        now = datetime.datetime.utcnow()
        scanner.accounts[0]['last_scan'] = now - datetime.timedelta(minutes=2)
        scanner.accounts[1]['last_scan'] = now - datetime.timedelta(minutes=15)
        scanner.accounts[2]['last_scan'] = now - datetime.timedelta(minutes=5)

        account = scanner.get_account()
        self.assertEqual('b', account['username'])

        now = datetime.datetime.utcnow()
        scanner.accounts[0]['last_scan'] = now - datetime.timedelta(minutes=2)
        scanner.accounts[1]['last_scan'] = now - datetime.timedelta(minutes=5)
        scanner.accounts[2]['last_scan'] = now - datetime.timedelta(minutes=6)

        account = scanner.get_account()
        self.assertIsNone(account)