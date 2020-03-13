# -*- coding: utf-8 -*-
import os
from unittest import TestCase
from decimal import Decimal
from datetime import datetime
import logging

from ofxstatement.plugins.fr.banquepopulaire import Plugin

logger = logging.getLogger(__name__)


class ParserTest(TestCase):

    def test_big(self):
        # Create and configure parser:
        here = os.path.dirname(__file__)
        text_filename = os.path.join(here, 'samples', 'Extrait_de_compte.txt')
        parser = Plugin(None, None).get_parser(text_filename)

        # And parse:
        statement = parser.parse()

        self.assertEqual(statement.currency, 'EUR')
        self.assertEqual(statement.bank_id, "CCBPFRPPBDX")
        self.assertEqual(statement.account_id, "99999999999")
        self.assertEqual(statement.account_type, "CHECKING")

        self.assertEqual(statement.start_balance, Decimal('401.99'))
        self.assertEqual(statement.start_date,
                         datetime.strptime("2019-06-04",
                                           parser.date_format).date())

        self.assertEqual(statement.end_balance, Decimal('2618.13'))
        self.assertEqual(statement.end_date,
                         datetime.strptime("2019-07-03",
                                           parser.date_format).date())

        self.assertEqual(len(statement.lines), 37)

        for idx, line in enumerate(statement.lines, start=1):
            assert isinstance(idx, int)
            if idx in [0, 4, 8, 9, 12, 14, 20, 29, 31]:
                self.assertIsNone(statement.lines[idx].check_no,
                                  'idx: %d' % (idx))
            else:
                self.assertIsNotNone(statement.lines[idx].check_no,
                                     'idx: %d' % (idx))

        self.assertEqual(statement.lines[0].amount, Decimal('55.00'))
        self.assertEqual(statement.lines[0].payee, '')
        self.assertEqual(statement.lines[0].memo, '')
        self.assertEqual(statement.lines[0].date, '')
        self.assertEqual(statement.lines[1].amount, Decimal('-39.57'))
        self.assertEqual(statement.lines[1].payee, '')
        self.assertEqual(statement.lines[1].memo, '')
        self.assertEqual(statement.lines[1].date, '')
        self.assertEqual(statement.lines[36].amount, Decimal('2750.00'))
