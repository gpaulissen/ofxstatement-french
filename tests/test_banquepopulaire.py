# -*- coding: utf-8 -*-
import os
from unittest import TestCase
from decimal import Decimal
from datetime import datetime
import pytest
import logging

from ofxstatement.plugins.fr.banquepopulaire import Plugin

logger = logging.getLogger(__name__)


def to_date(parser, s: str):
    return datetime.strptime(s, parser.date_format).date()


class ParserTest(TestCase):

    def _parse(self, text_filename):
        parser = Plugin(None, None).get_parser(text_filename)

        # And parse:
        stmt = parser.parse()

        self.assertEqual(stmt.currency, 'EUR')
        self.assertEqual(stmt.bank_id, "CCBPFRPPBDX")
        self.assertEqual(stmt.account_id, "99999999999")
        self.assertEqual(stmt.account_type, "CHECKING")

        self.assertEqual(stmt.start_balance, Decimal('401.99'))
        self.assertEqual(stmt.start_date, to_date(parser, "2019-06-04"))

        self.assertEqual(stmt.end_balance, Decimal('2618.13'))
        self.assertEqual(stmt.end_date, to_date(parser, "2019-07-03"))

        self.assertEqual(len(stmt.lines), 37)

        for idx, line in enumerate(stmt.lines, start=0):
            assert isinstance(idx, int)
            if idx in [0, 4, 8, 9, 12, 14, 20, 29, 31]:
                self.assertIsNone(stmt.lines[idx].check_no,
                                  'line[%d]: %s' % (idx, stmt.lines[idx]))
            else:
                self.assertIsNotNone(stmt.lines[idx].check_no,
                                     'line[%d]: %s' % (idx, stmt.lines[idx]))

        self.assertEqual(stmt.lines[0].amount, Decimal('55.00'))
        self.assertEqual(stmt.lines[0].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[0].memo, 'EVI M ------- -----')
        self.assertEqual(stmt.lines[0].date, to_date(parser, "2019-06-06"))

        self.assertEqual(stmt.lines[1].amount, Decimal('-39.57'))
        self.assertEqual(stmt.lines[1].payee, 'PRLV SEPA ---- ----')
        self.assertEqual(stmt.lines[1].memo,
                         '---------- --------- 999999999' + ' ' +
                         'xxxxxxxxxxxxxxxxxx')
        self.assertEqual(stmt.lines[1].date, to_date(parser, "2019-06-07"))
        self.assertEqual(stmt.lines[1].check_no, 'XXXXXXX')

        self.assertEqual(stmt.lines[2].amount, Decimal('-320.00'))
        self.assertEqual(stmt.lines[2].payee, 'VIREMENT')
        self.assertEqual(stmt.lines[2].memo,
                         'VIR --------------------')
        self.assertEqual(stmt.lines[2].date, to_date(parser, "2019-06-09"))
        self.assertEqual(stmt.lines[2].check_no, '9999999')

        self.assertEqual(stmt.lines[3].amount, Decimal('-80.00'))
        self.assertEqual(stmt.lines[3].payee, 'VIR MME ----------------')
        self.assertEqual(stmt.lines[3].memo,
                         'XXXXXXXX' + ' ' +
                         'xxxxxxxxxxxxxxx')
        self.assertEqual(stmt.lines[3].date, to_date(parser, "2019-06-11"))
        self.assertEqual(stmt.lines[3].check_no, '9999999')

        self.assertEqual(stmt.lines[4].amount, Decimal('3500.00'))
        self.assertEqual(stmt.lines[4].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[4].memo,
                         'EVI -----------------')
        self.assertEqual(stmt.lines[4].date, to_date(parser, "2019-06-11"))
        self.assertIsNone(stmt.lines[4].check_no)

        self.assertEqual(stmt.lines[5].amount, Decimal('-30.99'))
        self.assertEqual(stmt.lines[5].payee, 'PRLV SEPA --------')
        self.assertEqual(stmt.lines[5].memo,
                         '--------------------------' + ' ' +
                         '-----------')
        self.assertEqual(stmt.lines[5].date, to_date(parser, "2019-06-13"))
        self.assertEqual(stmt.lines[5].check_no, 'XXXXXXX')

        self.assertEqual(stmt.lines[6].amount, Decimal('-4.10'))
        self.assertEqual(stmt.lines[6].payee, 'FRAIS/VIREMENT')
        self.assertEqual(stmt.lines[6].memo,
                         '00001 OPERATION')
        self.assertEqual(stmt.lines[6].date, to_date(parser, "2019-06-13"))
        self.assertEqual(stmt.lines[6].check_no, '9999999')

        self.assertEqual(stmt.lines[7].amount, Decimal('-3500.00'))
        self.assertEqual(stmt.lines[7].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[7].memo,
                         'VIR SARL ------------')
        self.assertEqual(stmt.lines[7].date, to_date(parser, "2019-06-13"))
        self.assertEqual(stmt.lines[7].check_no, '9999999')

        self.assertEqual(stmt.lines[14].amount, Decimal('2500.00'))
        self.assertEqual(stmt.lines[14].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[14].memo,
                         'EVI -------- ---------')
        self.assertEqual(stmt.lines[14].date, to_date(parser, "2019-06-19"))
        self.assertIsNone(stmt.lines[14].check_no)

        self.assertEqual(stmt.lines[15].amount, Decimal('-43.70'))
        self.assertEqual(stmt.lines[15].payee, 'PRLV SEPA AUTOROUTES DU')
        self.assertEqual(stmt.lines[15].memo,
                         '---------------------------' + ' ' +
                         '-------------------')
        self.assertEqual(stmt.lines[15].date, to_date(parser, "2019-06-20"))
        self.assertEqual(stmt.lines[15].check_no, 'XXXXXXX')

        self.assertEqual(stmt.lines[21].amount, Decimal('-123.00'))
        self.assertEqual(stmt.lines[21].payee, '------ ----------')
        self.assertEqual(stmt.lines[21].memo,
                         '------ ------------ -----')
        self.assertEqual(stmt.lines[21].date, to_date(parser, "2019-06-25"))
        self.assertEqual(stmt.lines[21].check_no, 'XXXXXXX')

        self.assertEqual(stmt.lines[22].amount, Decimal('-7.18'))
        self.assertEqual(stmt.lines[22].payee, 'COTIS AFFINEA')
        self.assertEqual(stmt.lines[22].memo,
                         '-------- ----------------------' + ' ' +
                         'CONTRAT -------------')
        self.assertEqual(stmt.lines[22].date, to_date(parser, "2019-06-25"))
        self.assertEqual(stmt.lines[22].check_no, '9999999')

        self.assertEqual(stmt.lines[23].amount, Decimal('-12.18'))
        self.assertEqual(stmt.lines[23].payee, 'COTIS AFFINEA')
        self.assertEqual(stmt.lines[23].memo,
                         '-------- ----------------------' + ' ' +
                         '------- -------------')
        self.assertEqual(stmt.lines[23].date, to_date(parser, "2019-06-25"))
        self.assertEqual(stmt.lines[23].check_no, '9999999')

        self.assertEqual(stmt.lines[30].amount, Decimal('-200.00'))
        self.assertEqual(stmt.lines[30].payee, 'VIR MME -------- -------')
        self.assertEqual(stmt.lines[30].memo,
                         'rbst apport sur compte courant')
        self.assertEqual(stmt.lines[30].date, to_date(parser, "2019-06-30"))
        self.assertEqual(stmt.lines[30].check_no, '9999999')

        self.assertEqual(stmt.lines[31].amount, Decimal('6000.00'))
        self.assertEqual(stmt.lines[31].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[31].memo,
                         'EVI CASDEN B.P ENGT')
        self.assertEqual(stmt.lines[31].date, to_date(parser, "2019-07-01"))
        self.assertIsNone(stmt.lines[31].check_no)

        self.assertEqual(stmt.lines[36].amount, Decimal('-2750.00'))
        self.assertEqual(stmt.lines[36].payee, 'VIR M -------- ---------')
        self.assertEqual(stmt.lines[36].memo,
                         'xxxx')
        self.assertEqual(stmt.lines[36].date, to_date(parser, "2019-07-02"))
        self.assertEqual(stmt.lines[36].check_no, '9999999')

    def test_simple(self):
        # Create and configure parser:
        here = os.path.dirname(__file__)

        self._parse(os.path.join(here, 'samples', 'Extrait_de_compte.txt'))

    def test_full(self):
        # Create and configure parser:
        here = os.path.dirname(__file__)

        self._parse(os.path.join(here, 'samples', 'Extrait_de_compte_full.txt'))

    def test_balance(self):
        # Create and configure parser:
        here = os.path.dirname(__file__)

        parser = Plugin(None, None).get_parser(os.path.join(here, 'samples', 'Extrait_de_compte_balance.txt'))

        # And parse:
        stmt = parser.parse()

        self.assertEqual(stmt.currency, 'EUR')
        self.assertEqual(stmt.bank_id, "CCBPFRPPBDX")
        self.assertEqual(stmt.account_id, "99999999999")
        self.assertEqual(stmt.account_type, "CHECKING")

        self.assertEqual(stmt.start_balance, Decimal('-782.52'))
        self.assertEqual(stmt.start_date, to_date(parser, "2019-08-02"))

        self.assertEqual(stmt.end_balance, Decimal('131.48'))
        self.assertEqual(stmt.end_date, to_date(parser, "2019-09-04"))

        self.assertEqual(len(stmt.lines), 5)

    @pytest.mark.xfail(raises=AttributeError)
    def test_fail(self):
        """'Parser' object has no attribute 'bank_id'
        """
        here = os.path.dirname(__file__)
        pdf_filename = os.path.join(here, 'samples', 'blank.pdf')
        parser = Plugin(None, None).get_parser(pdf_filename)

        # And parse:
        parser.parse()
