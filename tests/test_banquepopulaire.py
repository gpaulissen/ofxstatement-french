# -*- coding: utf-8 -*-
import os
import sys
import traceback
from unittest import TestCase
from decimal import Decimal
from datetime import datetime, date
import pytest
import logging
from difflib import unified_diff

from ofxstatement.exceptions import ValidationError
from ofxstatement.plugins.fr.banquepopulaire import Plugin, StatementLine
from ofxstatement import ofx

logger = logging.getLogger(__name__)
here = os.path.dirname(__file__)


def dt(parser, s: str) -> datetime:
    return datetime.strptime(s, parser.date_format)


def d(parser, s: str) -> date:
    return dt(parser, s).date()


class ParserTest(TestCase):

    def assertStatementLine(self,
                            stmt_line: StatementLine,
                            amount: Decimal = None,
                            payee: str = None,
                            memo: str = None,
                            date=None,
                            check_no: str = None) -> None:
        if amount:
            self.assertEqual(stmt_line.amount, amount)
        if payee:
            self.assertEqual(stmt_line.payee, payee)
        if memo:
            self.assertEqual(stmt_line.memo, memo)
        if date:
            self.assertEqual(stmt_line.date, date)
        if check_no:
            self.assertEqual(stmt_line.check_no, check_no)

    def _parse(self, text_filename):
        parser = Plugin(None, None).get_parser(text_filename)

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()

        self.assertEqual(stmt.currency, 'EUR')
        self.assertEqual(stmt.bank_id, "CCBPFRPPBDX")
        self.assertEqual(stmt.account_id, "99999999999")
        self.assertEqual(stmt.account_type, "CHECKING")

        self.assertEqual(stmt.start_balance, Decimal('401.99'))
        self.assertEqual(stmt.start_date, dt(parser, "2019-06-04"))

        self.assertEqual(stmt.end_balance, Decimal('2618.13'))
        self.assertEqual(stmt.end_date, dt(parser, "2019-07-03"))

        self.assertEqual(len(stmt.lines), 37)

        for idx, line in enumerate(stmt.lines, start=0):
            assert isinstance(idx, int)
            if idx in [0, 4, 8, 9, 12, 14, 20, 29, 31]:
                self.assertIsNone(line.check_no,
                                  'line[%d]: %s' % (idx, line))
            else:
                self.assertIsNotNone(line.check_no,
                                     'line[%d]: %s' % (idx, line))

        self.assertEqual(stmt.lines[0].amount, Decimal('55.00'))
        self.assertEqual(stmt.lines[0].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[0].memo, 'EVI M ------- -----')
        self.assertEqual(stmt.lines[0].date, dt(parser, "2019-06-06"))

        self.assertEqual(stmt.lines[1].amount, Decimal('-39.57'))
        self.assertEqual(stmt.lines[1].payee, 'PRLV SEPA ---- ----')
        self.assertEqual(stmt.lines[1].memo,
                         '---------- --------- 999999999' + ' ' +
                         'xxxxxxxxxxxxxxxxxx')
        self.assertEqual(stmt.lines[1].date, dt(parser, "2019-06-07"))
        self.assertEqual(stmt.lines[1].check_no, 'XXXXXXX')

        self.assertEqual(stmt.lines[2].amount, Decimal('-320.00'))
        self.assertEqual(stmt.lines[2].payee, 'VIREMENT')
        self.assertEqual(stmt.lines[2].memo,
                         'VIR --------------------')
        self.assertEqual(stmt.lines[2].date, dt(parser, "2019-06-09"))
        self.assertEqual(stmt.lines[2].check_no, '9999999')

        self.assertEqual(stmt.lines[3].amount, Decimal('-80.00'))
        self.assertEqual(stmt.lines[3].payee, 'VIR MME ----------------')
        self.assertEqual(stmt.lines[3].memo,
                         'XXXXXXXX' + ' ' +
                         'xxxxxxxxxxxxxxx')
        self.assertEqual(stmt.lines[3].date, dt(parser, "2019-06-11"))
        self.assertEqual(stmt.lines[3].check_no, '9999999')

        self.assertEqual(stmt.lines[4].amount, Decimal('3500.00'))
        self.assertEqual(stmt.lines[4].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[4].memo,
                         'EVI -----------------')
        self.assertEqual(stmt.lines[4].date, dt(parser, "2019-06-11"))
        self.assertIsNone(stmt.lines[4].check_no)

        self.assertEqual(stmt.lines[5].amount, Decimal('-30.99'))
        self.assertEqual(stmt.lines[5].payee, 'PRLV SEPA --------')
        self.assertEqual(stmt.lines[5].memo,
                         '--------------------------' + ' ' +
                         '-----------')
        self.assertEqual(stmt.lines[5].date, dt(parser, "2019-06-13"))
        self.assertEqual(stmt.lines[5].check_no, 'XXXXXXX')

        self.assertEqual(stmt.lines[6].amount, Decimal('-4.10'))
        self.assertEqual(stmt.lines[6].payee, 'FRAIS/VIREMENT')
        self.assertEqual(stmt.lines[6].memo,
                         '00001 OPERATION')
        self.assertEqual(stmt.lines[6].date, dt(parser, "2019-06-13"))
        self.assertEqual(stmt.lines[6].check_no, '9999999')

        self.assertEqual(stmt.lines[7].amount, Decimal('-3500.00'))
        self.assertEqual(stmt.lines[7].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[7].memo,
                         'VIR SARL ------------')
        self.assertEqual(stmt.lines[7].date, dt(parser, "2019-06-13"))
        self.assertEqual(stmt.lines[7].check_no, '9999999')

        self.assertEqual(stmt.lines[14].amount, Decimal('2500.00'))
        self.assertEqual(stmt.lines[14].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[14].memo,
                         'EVI -------- ---------')
        self.assertEqual(stmt.lines[14].date, dt(parser, "2019-06-19"))
        self.assertIsNone(stmt.lines[14].check_no)

        self.assertEqual(stmt.lines[15].amount, Decimal('-43.70'))
        self.assertEqual(stmt.lines[15].payee, 'PRLV SEPA AUTOROUTES DU')
        self.assertEqual(stmt.lines[15].memo,
                         '---------------------------' + ' ' +
                         '-------------------')
        self.assertEqual(stmt.lines[15].date, dt(parser, "2019-06-20"))
        self.assertEqual(stmt.lines[15].check_no, 'XXXXXXX')

        self.assertEqual(stmt.lines[21].amount, Decimal('-123.00'))
        self.assertEqual(stmt.lines[21].payee, '------ ----------')
        self.assertEqual(stmt.lines[21].memo,
                         '------ ------------ -----')
        self.assertEqual(stmt.lines[21].date, dt(parser, "2019-06-25"))
        self.assertEqual(stmt.lines[21].check_no, 'XXXXXXX')

        self.assertEqual(stmt.lines[22].amount, Decimal('-7.18'))
        self.assertEqual(stmt.lines[22].payee, 'COTIS AFFINEA')
        self.assertEqual(stmt.lines[22].memo,
                         '-------- ----------------------' + ' ' +
                         'CONTRAT -------------')
        self.assertEqual(stmt.lines[22].date, dt(parser, "2019-06-26"))
        self.assertEqual(stmt.lines[22].check_no, '9999999')

        self.assertEqual(stmt.lines[23].amount, Decimal('-12.18'))
        self.assertEqual(stmt.lines[23].payee, 'COTIS AFFINEA')
        self.assertEqual(stmt.lines[23].memo,
                         '-------- ----------------------' + ' ' +
                         '------- -------------')
        self.assertEqual(stmt.lines[23].date, dt(parser, "2019-06-26"))
        self.assertEqual(stmt.lines[23].check_no, '9999999')

        self.assertEqual(stmt.lines[30].amount, Decimal('-200.00'))
        self.assertEqual(stmt.lines[30].payee, 'VIR MME -------- -------')
        self.assertEqual(stmt.lines[30].memo,
                         'rbst apport sur compte courant')
        self.assertEqual(stmt.lines[30].date, dt(parser, "2019-06-30"))
        self.assertEqual(stmt.lines[30].check_no, '9999999')

        self.assertEqual(stmt.lines[31].amount, Decimal('6000.00'))
        self.assertEqual(stmt.lines[31].payee, 'VIREMENT SEPA')
        self.assertEqual(stmt.lines[31].memo,
                         'EVI CASDEN B.P ENGT')
        self.assertEqual(stmt.lines[31].date, dt(parser, "2019-07-01"))
        self.assertIsNone(stmt.lines[31].check_no)

        self.assertEqual(stmt.lines[36].amount, Decimal('-2750.00'))
        self.assertEqual(stmt.lines[36].payee, 'VIR M -------- ---------')
        self.assertEqual(stmt.lines[36].memo,
                         'xxxx')
        self.assertEqual(stmt.lines[36].date, dt(parser, "2019-07-02"))
        self.assertEqual(stmt.lines[36].check_no, '9999999')

    def test_simple(self):
        # Create and configure parser:
        self._parse(os.path.join(here, 'samples', 'Extrait_de_compte.txt'))

    def test_full(self):
        # Create and configure parser:
        self._parse(os.path.join(here,
                                 'samples',
                                 'Extrait_de_compte_full.txt'))

    def test_balance(self):
        # Create and configure parser:
        cfg = {'ofx_files': '*.ofx'}
        plugin = Plugin(None, cfg)
        parser = plugin.get_parser(
            os.path.join(here,
                         'samples',
                         'Extrait_de_compte_balance.txt'))

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()

        self.assertEqual(stmt.currency, 'EUR')
        self.assertEqual(stmt.bank_id, "CCBPFRPPBDX")
        self.assertEqual(stmt.account_id, "99999999999")
        self.assertEqual(stmt.account_type, "CHECKING")

        self.assertEqual(stmt.start_balance, Decimal('0.00'))
        self.assertEqual(stmt.start_date, dt(parser, "2019-08-02"))

        self.assertEqual(stmt.end_balance, Decimal('808.00'))
        self.assertEqual(stmt.end_date, dt(parser, "2019-09-04"))

        self.assertEqual(len(stmt.lines), 6)
        for idx, line in enumerate(stmt.lines, start=1):
            if idx == 2:
                self.assertEqual(line.id,
                                 '9f31f229e78929ef4fbace80d105187bea827392')
            elif idx == 3:
                self.assertEqual(line.id,
                                 '9f31f229e78929ef4fbace80d105187bea8273921-1')
            elif idx == 4:
                self.assertEqual(line.id, str(idx))
                # These values are taken from the cache
                self.assertEqual(line.date, dt(parser, "2019-06-20"))
                # fields are not overwritten unless empty
                self.assertEqual(line.payee, 'COM INTERVENTION')
                self.assertEqual(line.memo,
                                 'XXXXXXXX 9999999999999999999999 1 OPERATION')
            else:
                # Statement lines 1, 4, 5 and 6 should have that FITID,
                # so line 5 has FITID 5.
                self.assertEqual(line.id, str(idx), line)

    def test_january(self):
        # Create and configure parser:
        plugin = Plugin(None, None)
        parser = plugin.get_parser(
            os.path.join(here,
                         'samples',
                         'Extrait_de_compte_janvier.txt'))

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()
        self.assertEqual(stmt.currency, 'EUR')
        self.assertEqual(stmt.bank_id, "CCBPFRPPBDX")
        self.assertEqual(stmt.account_id, "99999999999")
        self.assertEqual(stmt.account_type, "CHECKING")

        self.assertEqual(stmt.start_balance, Decimal('981.04'))
        self.assertEqual(stmt.start_date, dt(parser, "2019-12-03"))

        self.assertEqual(stmt.end_balance, Decimal('30.86'))
        self.assertEqual(stmt.end_date, dt(parser, "2020-01-03"))

        self.assertEqual(len(stmt.lines), 45)

    def test_january_2021(self):
        # Create and configure parser:
        plugin = Plugin(None, {'bank_id': 'CCBPFRPPBDX'})
        parser = plugin.get_parser(
            os.path.join(here,
                         'samples',
                         'Extrait_de_compte_janvier_2021.txt'))

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()
        self.assertEqual(stmt.currency, 'EUR')
        self.assertEqual(stmt.bank_id, "CCBPFRPPBDX")
        self.assertEqual(stmt.account_id, "99999999999")
        self.assertEqual(stmt.account_type, "CHECKING")

        self.assertEqual(stmt.start_balance, Decimal('6010.50'))
        self.assertEqual(stmt.start_date, dt(parser, "2020-01-02"))

        self.assertEqual(stmt.end_balance, Decimal('6000.00'))
        self.assertEqual(stmt.end_date, dt(parser, "2021-01-05"))

        self.assertEqual(len(stmt.lines), 27)

    @pytest.mark.xfail(raises=ValidationError)
    def test_fail(self):
        """'Parser' object has no attribute 'bank_id'
        """
        pdf_filename = os.path.join(here, 'samples', 'blank.pdf')
        parser = Plugin(None, None).get_parser(pdf_filename)

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()

    @pytest.mark.xfail(raises=ValidationError)
    def test_fail_january_2021(self):
        # Create and configure parser:
        plugin = Plugin(None, None)
        parser = plugin.get_parser(
            os.path.join(here,
                         'samples',
                         'Extrait_de_compte_janvier_2021.txt'))

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()

    @pytest.mark.xfail(raises=ValidationError)
    def test_fail_ofx_files(self):
        """'Parser' object has no attribute 'bank_id'
        """
        pdf_filename = os.path.join(here, 'samples', 'blank.pdf')
        cfg = {'ofx_files': '~/*.ofx'}
        plugin = Plugin(None, cfg)
        parser = plugin.get_parser(pdf_filename)

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()

    def test_20220802(self):
        """
        The cache file (BPACA_OP_20220802.ofx) contains FITIDs with spaces
        so Extrait-de-compte-20220802.pdf.txt too.
        """
        cfg = {'ofx_files': 'BPACA_OP_20220717*.ofx,BPACA_OP_20220802.ofx'}
        plugin = Plugin(None, cfg)
        base = 'Extrait-de-compte-20220802.pdf'
        input_file = os.path.join(here, 'samples', f'{base}.txt')
        output_file_expected = os.path.join(here, 'samples', f'{base}.ofx')
        # add a dot in front so it will be ignored by VCS
        output_file_actual = os.path.join(here, 'samples', f'.{base}.ofx')
        parser = plugin.get_parser(input_file)

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()

        for idx, line in enumerate(stmt.lines, start=0):
            logger.debug('line %d: %s', idx, line)
            if idx >= 57:
                self.assertTrue(' ' in line.id)
            else:
                self.assertFalse(' ' in line.id)

        # Check file contents
        with open(output_file_actual, "w") as out:
            writer = ofx.OfxWriter(stmt)
            out.write(writer.toxml(pretty=True))

        with open(output_file_expected, "r") as f:
            expected_lines = f.readlines()
        with open(output_file_actual, "r") as f:
            actual_lines = f.readlines()

        diff = list(unified_diff(expected_lines, actual_lines))
        try:
            assert diff == [], "Unexpected file contents:\n" + "".join(diff)
            self.assertFalse(len(diff) == 0)
        except Exception:
            self.assertEquals(len(diff), 67)

    def test_20220828(self):
        """
        The cache file (BPACA_OP_20220802.ofx) contains FITIDs with spaces.
        The cache file (BPACA_OP_20220828.ofx) does NOT.
        So Extrait-de-compte-20220802.pdf.txt neither.
        """
        cfg = {'ofx_files': 'BPACA_OP_202208??.ofx'}
        plugin = Plugin(None, cfg)
        parser = plugin.get_parser(
            os.path.join(here,
                         'samples',
                         'Extrait-de-compte-20220802.pdf.txt'))

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()

        for idx, line in enumerate(stmt.lines, start=0):
            logger.debug('line %d: %s', idx, line)
            if idx == 57:
                self.assertTrue(' ' in line.id)
            else:
                self.assertFalse(' ' in line.id)

    def test_20220902(self):
        """
        The cache file (BPACA_OP_20220802.ofx) contains FITIDs with spaces.
        The cache file (BPACA_OP_20220828.ofx) does NOT.
        So Extrait-de-compte-20220902.pdf.txt neither.
        """
        cfg = {'ofx_files': 'BPACA_OP_202208??.ofx'}
        plugin = Plugin(None, cfg)
        parser = plugin.get_parser(
            os.path.join(here,
                         'samples',
                         'Extrait-de-compte-20220902.pdf.txt'))

        # And parse:
        stmt = parser.parse()

        stmt.assert_valid()

        for idx, line in enumerate(stmt.lines, start=0):
            self.assertFalse(' ' in line.id)

#    @pytest.mark.xfail(raises=ValidationError)
    def test_20231130(self):
        """
        Extrait-de-compte-20231130.pdf.txt can not be parsed (yet).
        """
        try:
            plugin = Plugin(None, {'bank_id': 'CCBPFRPPBDX'})
            parser = plugin.get_parser(
                os.path.join(here,
                             'samples',
                             'Extrait-de-compte-20231130.pdf.txt'))

            # And parse:
            stmt = parser.parse()

            stmt.assert_valid()
            self.assertEqual(stmt.currency, 'EUR')
            self.assertEqual(stmt.bank_id, "CCBPFRPPBDX")
            self.assertEqual(stmt.account_id, "99999999999")
            self.assertEqual(stmt.account_type, "CHECKING")

            self.assertEqual(stmt.start_balance, Decimal('3090.90'))
            self.assertEqual(stmt.start_date, dt(parser, "2023-10-31"))

            self.assertEqual(stmt.end_balance, Decimal('3426.71'))
            # add one day: start balance <= transactions < end balance
            self.assertEqual(stmt.end_date, dt(parser, "2023-12-01"))

#            self.assertEqual(len(stmt.lines), 27 + 27)

            self.assertStatementLine(stmt.lines[0],
                                     amount=Decimal('-350.00'),
                                     payee='011123 CB****1352',
                                     memo='CIC BORDEAUX FR BORDEAUX 350,00EUR 1 EURO = 1,000000',  # nopep8
                                     date=dt(parser, "2023-11-02"),
                                     check_no='E2Q9LXC')
            self.assertStatementLine(stmt.lines[1],
                                     amount=Decimal('-8.10'),
                                     check_no='E2QCAQH',
                                     date=datetime(2023, 11, 2, 0, 0),
                                     memo='SAVEURS ET TRAD30BORDEAUX',
                                     payee='311023 CB****3735')
            self.assertStatementLine(stmt.lines[2],
                                     amount=Decimal('-24.70'),
                                     check_no='E2QCAQI',
                                     date=datetime(2023, 11, 2, 0, 0),
                                     memo='PHARMABREDE           30BORDEAUX',
                                     payee='311023 CB****3735')
            self.assertStatementLine(stmt.lines[3],
                                     amount=Decimal('-364.50'),
                                     check_no='E2QCAQJ',
                                     date=datetime(2023, 11, 2, 0, 0),
                                     memo='LES CHALETS SEC66BOLQUERE',
                                     payee='011123 CB****3735')
            self.assertStatementLine(stmt.lines[4],
                                     amount=Decimal('-54.40'),
                                     check_no='0000429',
                                     date=datetime(2023, 11, 3, 0, 0),
                                     memo='',
                                     payee='CHEQUE')
            self.assertStatementLine(stmt.lines[5],
                                     amount=Decimal('-1461.89'),
                                     check_no='8891338',
                                     date=datetime(2023, 11, 3, 0, 0),
                                     memo='DONT CAP 909,00 ASS. 159,29E INT. 393,60 COM. 0,00E',  # nopep8
                                     payee='ECHEANCE PRET')
            self.assertStatementLine(stmt.lines[6],
                                     amount=Decimal('500.00'),
                                     check_no='0812417',
                                     date=datetime(2023, 11, 3, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR MME SEVERINE PUILLET')
            self.assertStatementLine(stmt.lines[7],
                                     amount=Decimal('-46.99'),
                                     check_no='E4VPOWB',
                                     date=datetime(2023, 11, 3, 0, 0),
                                     memo='HELLOFRESH NL Amsterdam 46,99EUR 1 EURO = 1,000000',  # nopep8
                                     payee='031123 CB****1352')
            self.assertStatementLine(stmt.lines[8],
                                     amount=Decimal('34.00'),
                                     check_no=None,
                                     date=datetime(2023, 11, 6, 0, 0),
                                     memo='EVI APRIL SANTE PREVOYAN',
                                     payee='VIREMENT SEPA')
            self.assertStatementLine(stmt.lines[9],
                                     amount=Decimal('-201.34'),
                                     check_no='0FUY5NC',
                                     date=datetime(2023, 11, 6, 0, 0),
                                     memo='Numero de client : 6022926937 - MM9760229269370001',  # nopep8
                                     payee='PRLV SEPA EDF clients pa')
            self.assertStatementLine(stmt.lines[10],
                                     amount=Decimal('-339.53'),
                                     check_no='0FUYJBX',
                                     date=datetime(2023, 11, 6, 0, 0),
                                     memo='999999999 DC37304264780EDIAC DC999999999999',  # nopep8
                                     payee='PRLV SEPA DIAC')
            self.assertStatementLine(stmt.lines[11],
                                     amount=Decimal('-8.55'),
                                     check_no='E9CJDJO',
                                     date=datetime(2023, 11, 6, 0, 0),
                                     memo='SAVEURS ET TRAD30BORDEAUX',
                                     payee='041123 CB****3735')
            self.assertStatementLine(stmt.lines[12],
                                     amount=Decimal('-14.00'),
                                     check_no='E9CJDJP',
                                     date=datetime(2023, 11, 6, 0, 0),
                                     memo='BOULANGERIE MAL30BORDEAUX',
                                     payee='041123 CB****3735')
            self.assertStatementLine(stmt.lines[13],
                                     amount=Decimal('-48.16'),
                                     check_no='E9CJDJQ',
                                     date=datetime(2023, 11, 6, 0, 0),
                                     memo='LOULOU PRIMEUR 30BORDEAUX',
                                     payee='041123 CB****3735')
            self.assertStatementLine(stmt.lines[14],
                                     amount=Decimal('-3.46'),
                                     check_no='ECNJ2VE',
                                     date=datetime(2023, 11, 8, 0, 0),
                                     memo="L'AUTHENTIQUE S30BORDEAUX",
                                     payee='071123 CB****3735')
            self.assertStatementLine(stmt.lines[15],
                                     amount=Decimal('-4.10'),
                                     check_no='ECNJ2VF',
                                     date=datetime(2023, 11, 8, 0, 0),
                                     memo='BOULANGERIE MAL30BORDEAUX',
                                     payee='071123 CB****3735')
            self.assertStatementLine(stmt.lines[16],
                                     amount=Decimal('-5.80'),
                                     check_no='ECNJ2VG',
                                     date=datetime(2023, 11, 8, 0, 0),
                                     memo="L'AUTHENTIQUE S30BORDEAUX",
                                     payee='071123 CB****3735')
            self.assertStatementLine(stmt.lines[17],
                                     amount=Decimal('-11.52'),
                                     check_no='ECNJ2VH',
                                     date=datetime(2023, 11, 8, 0, 0),
                                     memo='FAURE ALLIN       30BORDEAUX',
                                     payee='071123 CB****3735')
            self.assertStatementLine(stmt.lines[18],
                                     amount=Decimal('1000.00'),
                                     check_no='0812425',
                                     date=datetime(2023, 11, 8, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN GERARDUS')
            self.assertStatementLine(stmt.lines[19],
                                     amount=Decimal('-500.00'),
                                     check_no='5800825',
                                     date=datetime(2023, 11, 9, 0, 0),
                                     memo='Virement de Compte Commun Virement de Compte Commun',  # nopep8
                                     payee='VIR Gert-Jan Perpignan')
            self.assertStatementLine(stmt.lines[20],
                                     amount=Decimal('324.30'),
                                     check_no=None,
                                     date=datetime(2023, 11, 9, 0, 0),
                                     memo='EVI ELECTRICITE DE FRANC',
                                     payee='VIREMENT SEPA')
            self.assertStatementLine(stmt.lines[21],
                                     amount=Decimal('-62.37'),
                                     check_no='0FWWRKS',
                                     date=datetime(2023, 11, 10, 0, 0),
                                     memo='Cotisation Assurance 999999999 17IARD999999999001',  # nopep8
                                     payee='PRLV SEPA BPCE IARD')
            self.assertStatementLine(stmt.lines[22],
                                     amount=Decimal('-250.00'),
                                     check_no='0FWW39S',
                                     date=datetime(2023, 11, 10, 0, 0),
                                     memo='01D130103319        11/23 2898FKBWV VAAIV5181035',  # nopep8
                                     payee='PRLV SEPA ABEILLE RETRAI')
            self.assertStatementLine(stmt.lines[23],
                                     amount=Decimal('-15.00'),
                                     check_no='0FWSB75',
                                     date=datetime(2023, 11, 10, 0, 0),
                                     memo='VOTRE DON CRF - F4693193 C20R19F1SPSY000000401744',  # nopep8
                                     payee='PRLV SEPA LA CROIX ROUGE')
            self.assertStatementLine(stmt.lines[24],
                                     amount=Decimal('-275.00'),
                                     check_no='0FW3G06',
                                     date=datetime(2023, 11, 10, 0, 0),
                                     memo='FACTURE OCTOBRE 000515',
                                     payee='PRLV SEPA FPMTM')
            self.assertStatementLine(stmt.lines[25],
                                     amount=Decimal('-46.99'),
                                     check_no='EGGH386',
                                     date=datetime(2023, 11, 10, 0, 0),
                                     memo='HELLOFRESH NL Amsterdam 46,99EUR 1 EURO = 1,000000',  # nopep8
                                     payee='101123 CB****1352')
            self.assertStatementLine(stmt.lines[26],
                                     amount=Decimal('-8.40'),
                                     check_no='EKXAO4A',
                                     date=datetime(2023, 11, 13, 0, 0),
                                     memo='BOULANGERIE MAL30BORDEAUX',
                                     payee='101123 CB****3735')
            self.assertStatementLine(stmt.lines[27],
                                     amount=Decimal('-15.23'),
                                     check_no='EKXAO4B',
                                     date=datetime(2023, 11, 13, 0, 0),
                                     memo='biocoop       30BORDEAUX',
                                     payee='101123 CB****3735')
            self.assertStatementLine(stmt.lines[28],
                                     amount=Decimal('-126.56'),
                                     check_no='EKXAO4C',
                                     date=datetime(2023, 11, 13, 0, 0),
                                     memo='AUCHAN 1345M 30BORDEAUX',
                                     payee='101123 CB****3735')
            self.assertStatementLine(stmt.lines[29],
                                     amount=Decimal('-189.00'),
                                     check_no='5984506',
                                     date=datetime(2023, 11, 14, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR MME SEVERINE PUILLET')
            self.assertStatementLine(stmt.lines[30],
                                     amount=Decimal('5.99'),
                                     check_no='EMKPPY9',
                                     date=datetime(2023, 11, 14, 0, 0),
                                     memo='AUCHAN 1345M DONT FRAIS: 0,00E 5,99EUR 1 EURO = 1,000000',  # nopep8
                                     payee='131123 CB****1352')
            self.assertStatementLine(stmt.lines[31],
                                     amount=Decimal('-1.00'),
                                     check_no='EN2MC6O',
                                     date=datetime(2023, 11, 14, 0, 0),
                                     memo='Fonds de dotatiFR Lesquin 1,00EUR 1 EURO = 1,000000',  # nopep8
                                     payee='131123 CB****1352')
            self.assertStatementLine(stmt.lines[32],
                                     amount=Decimal('-6.19'),
                                     check_no='EN2MC6P',
                                     date=datetime(2023, 11, 14, 0, 0),
                                     memo='Boulanger   FR VILLENAVE DO 6,19EUR 1 EURO = 1,000000',  # nopep8
                                     payee='131123 CB****1352')
            self.assertStatementLine(stmt.lines[33],
                                     amount=Decimal('-10.00'),
                                     check_no='EN2MC6Q',
                                     date=datetime(2023, 11, 14, 0, 0),
                                     memo='COUSTUT      FR 33 BEAUTIRAN 10,00EUR 1 EURO = 1,000000',  # nopep8
                                     payee='131123 CB****1352')
            self.assertStatementLine(stmt.lines[34],
                                     amount=Decimal('-100.00'),
                                     check_no='0000432',
                                     date=datetime(2023, 11, 15, 0, 0),
                                     memo='',
                                     payee='CHEQUE')
            self.assertStatementLine(stmt.lines[35],
                                     amount=Decimal('-5.70'),
                                     check_no='EPVTY1Q',
                                     date=datetime(2023, 11, 16, 0, 0),
                                     memo='PHARMABREDE           30BORDEAUX',
                                     payee='151123 CB****3735')
            self.assertStatementLine(stmt.lines[36],
                                     amount=Decimal('-26.50'),
                                     check_no='EPVTY1R',
                                     date=datetime(2023, 11, 16, 0, 0),
                                     memo='DR BUI MURIEL S30BORDEAUX',
                                     payee='151123 CB****3735')
            self.assertStatementLine(stmt.lines[37],
                                     amount=Decimal('1000.00'),
                                     check_no='0812425',
                                     date=datetime(2023, 11, 17, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN GERARDUS')
            self.assertStatementLine(stmt.lines[38],
                                     amount=Decimal('-27.83'),
                                     check_no='ES18KFS',
                                     date=datetime(2023, 11, 17, 0, 0),
                                     memo='AUCHAN 1345M FR BORDEAUX 27,83EUR 1 EURO = 1,000000',  # nopep8
                                     payee='161123 CB****1352')
            self.assertStatementLine(stmt.lines[39],
                                     amount=Decimal('-46.99'),
                                     check_no='ES18KFT',
                                     date=datetime(2023, 11, 17, 0, 0),
                                     memo='HelloFresh FranNL Amsterdam 46,99EUR 1 EURO = 1,000000',  # nopep8
                                     payee='171123 CB****1352')
            self.assertStatementLine(stmt.lines[40],
                                     amount=Decimal('-98.00'),
                                     check_no='ES18KFU',
                                     date=datetime(2023, 11, 17, 0, 0),
                                     memo='LA REDOUTE FR FR 59ROUBAIX 98,00EUR 1 EURO = 1,000000',  # nopep8
                                     payee='161123 CB****1352')
            self.assertStatementLine(stmt.lines[41],
                                     amount=Decimal('13.05'),
                                     check_no=None,
                                     date=datetime(2023, 11, 20, 0, 0),
                                     memo='EVI C.P.A.M. BORDEAUX',
                                     payee='VIREMENT SEPA')
            self.assertStatementLine(stmt.lines[42],
                                     amount=Decimal('-220.50'),
                                     check_no='0FXJILQ',
                                     date=datetime(2023, 11, 20, 0, 0),
                                     memo='JJ012017380043243669 102023 9999999999999999999',  # nopep8
                                     payee='PRLV SEPA Autoroutes du')
            self.assertStatementLine(stmt.lines[43],
                                     amount=Decimal('-1.34'),
                                     check_no='EWI2ARG',
                                     date=datetime(2023, 11, 20, 0, 0),
                                     memo='MONET DISTRIBUT78BOUGIVAL',
                                     payee='171123 CB****3735')
            self.assertStatementLine(stmt.lines[44],
                                     amount=Decimal('-4.95'),
                                     check_no='EWZYEVF',
                                     date=datetime(2023, 11, 20, 0, 0),
                                     memo='RATP       FR PARIS 4,95EUR 1 EURO = 1,000000',  # nopep8
                                     payee='171123 CB****1352')
            self.assertStatementLine(stmt.lines[45],
                                     amount=Decimal('-4.95'),
                                     check_no='EWZYEVG',
                                     date=datetime(2023, 11, 20, 0, 0),
                                     memo='RATP       FR PARIS 4,95EUR 1 EURO = 1,000000 #2',  # nopep8
                                     payee='171123 CB****1352')
            self.assertStatementLine(stmt.lines[46],
                                     amount=Decimal('-18.90'),
                                     check_no='EWZYEVH',
                                     date=datetime(2023, 11, 20, 0, 0),
                                     memo='RATP       FR PARIS 18,90EUR 1 EURO = 1,000000',  # nopep8
                                     payee='191123 CB****1352')
            self.assertStatementLine(stmt.lines[47],
                                     amount=Decimal('-11.68'),
                                     check_no='0010769',
                                     date=datetime(2023, 11, 21, 0, 0),
                                     memo='XCCNV066 2023111800010769000001 CONTRAT CNV9999999999',  # nopep8
                                     payee='COTIS FAMILLE CONFORT')
            self.assertStatementLine(stmt.lines[48],
                                     amount=Decimal('-2.00'),
                                     check_no='EY5IIGA',
                                     date=datetime(2023, 11, 21, 0, 0),
                                     memo='E. LECLERC        33BORDEAUX',
                                     payee='201123 CB****3735')
            self.assertStatementLine(stmt.lines[49],
                                     amount=Decimal('-2.90'),
                                     check_no='EYNDQZL',
                                     date=datetime(2023, 11, 21, 0, 0),
                                     memo='BOULANGERIE MALFR BORDEAUX 2,90EUR 1 EURO = 1,000000',  # nopep8
                                     payee='201123 CB****1352')
            self.assertStatementLine(stmt.lines[50],
                                     amount=Decimal('-14.60'),
                                     check_no='F1GLDSB',
                                     date=datetime(2023, 11, 23, 0, 0),
                                     memo="L'APARTE        33BORDEAUX",
                                     payee='221123 CB****3735')
            self.assertStatementLine(stmt.lines[51],
                                     amount=Decimal('7.95'),
                                     check_no=None,
                                     date=datetime(2023, 11, 24, 0, 0),
                                     memo='EVI APRIL SANTE PREVOYAN',
                                     payee='VIREMENT SEPA')
            self.assertStatementLine(stmt.lines[52],
                                     amount=Decimal('-14.50'),
                                     check_no='F344O9L',
                                     date=datetime(2023, 11, 24, 0, 0),
                                     memo='BOULANGERIE MAL30BORDEAUX',
                                     payee='231123 CB****3735')
            self.assertStatementLine(stmt.lines[53],
                                     amount=Decimal('-47.25'),
                                     check_no='F344O9M',
                                     date=datetime(2023, 11, 24, 0, 0),
                                     memo="L'AUTHENTIQUE 30BORDEAUX",
                                     payee='231123 CB****3735')
            self.assertStatementLine(stmt.lines[54],
                                     amount=Decimal('-46.99'),
                                     check_no='F3LZZFG',
                                     date=datetime(2023, 11, 24, 0, 0),
                                     memo='HelloFresh FranNL Amsterdam 46,99EUR 1 EURO = 1,000000',  # nopep8
                                     payee='241123 CB****1352')
            self.assertStatementLine(stmt.lines[55],
                                     amount=Decimal('-45.82'),
                                     check_no='0FZ9YWX',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='Votre abonnement mobile: 06XXXXX ++M0003437178',  # nopep8
                                     payee='PRLV SEPA Orange SA')
            self.assertStatementLine(stmt.lines[56],
                                     amount=Decimal('-299.00'),
                                     check_no='0FZDCZ1',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='SOLDE IMPOT REVENUS 2022 N DE FA NNFR46ZZZ0050021E33A0A206020PAS1',  # nopep8
                                     payee='PRLV SEPA DIRECTION GENE')
            self.assertStatementLine(stmt.lines[57],
                                     amount=Decimal('-1.90'),
                                     check_no='F82U0KD',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='CLINIQ BX TONDU33FLOIRAC',
                                     payee='241123 CB****3735')
            self.assertStatementLine(stmt.lines[58],
                                     amount=Decimal('-4.30'),
                                     check_no='F82U0KE',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='BOULANGERIE MAL30BORDEAUX',
                                     payee='251123 CB****3735')
            self.assertStatementLine(stmt.lines[59],
                                     amount=Decimal('-40.16'),
                                     check_no='F82U0KF',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='LOULOU PRIMEUR 30BORDEAUX',
                                     payee='251123 CB****3735')
            self.assertStatementLine(stmt.lines[60],
                                     amount=Decimal('-43.08'),
                                     check_no='F82U0KG',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='DR CUCLOS         33BORDEAUX',
                                     payee='241123 CB****3735')
            self.assertStatementLine(stmt.lines[61],
                                     amount=Decimal('-364.50'),
                                     check_no='F82U0KH',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='LES CHALETS SEC66BOLQUERE',
                                     payee='251123 CB****3735')
            self.assertStatementLine(stmt.lines[62],
                                     amount=Decimal('-40.43'),
                                     check_no='F8KQ600',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='AUCHAN 1345M FR BORDEAUX 40,43EUR 1 EURO = 1,000000',  # nopep8
                                     payee='241123 CB****1352')
            self.assertStatementLine(stmt.lines[63],
                                     amount=Decimal('-50.28'),
                                     check_no='F8KQ601',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='AUCHAN 1345M FR BORDEAUX 50,28EUR 1 EURO = 1,000000',  # nopep8
                                     payee='241123 CB****1352')
            self.assertStatementLine(stmt.lines[64],
                                     amount=Decimal('500.00'),
                                     check_no='0812425',
                                     date=datetime(2023, 11, 27, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN GERARDUS')
            self.assertStatementLine(stmt.lines[65],
                                     amount=Decimal('3000.00'),
                                     check_no='JWND1BS',
                                     date=datetime(2023, 11, 29, 0, 0),
                                     memo='salaire 2023-11',
                                     payee='VIR SAS PAULISSOFT')
            self.assertStatementLine(stmt.lines[66],
                                     amount=Decimal('-11.65'),
                                     check_no='FBDTG1H',
                                     date=datetime(2023, 11, 29, 0, 0),
                                     memo='SOL EN BIO        30BORDEAUX',
                                     payee='281123 CB****3735')
        except Exception as e:
            _, _, tb = sys.exc_info()
            traceback.print_tb(tb)  # Fixed format
            tb_info = traceback.extract_tb(tb)
            filename, line, func, text = tb_info[-1]
            logger.error('Error line {}; statement "{}"'.format(line, text))
            raise e

    def test_20240102(self):
        """
        Extrait-de-compte-20220902.pdf.txt can not be parsed (yet).
        """
        try:
            plugin = Plugin(None, {'bank_id': 'CCBPFRPPBDX'})
            parser = plugin.get_parser(
                os.path.join(here,
                             'samples',
                             'Extrait-de-compte-20240102.pdf.txt'))

            # And parse:
            stmt = parser.parse()

            stmt.assert_valid()
            self.assertEqual(stmt.currency, 'EUR')
            self.assertEqual(stmt.bank_id, "CCBPFRPPBDX")
            self.assertEqual(stmt.account_id, "99999999999")
            self.assertEqual(stmt.account_type, "CHECKING")

            self.assertEqual(stmt.start_balance, Decimal('5954.72'))
            self.assertEqual(stmt.start_date, dt(parser, "2023-01-02"))

            self.assertEqual(stmt.end_balance, Decimal('15.32'))
            self.assertEqual(stmt.end_date, dt(parser, "2024-01-03"))

            self.assertEqual(len(stmt.lines), 15)

            for idx, line in enumerate(stmt.lines, start=1):
                assert isinstance(idx, int)
                self.assertIsNotNone(line.check_no,
                                     'line[%d]: %s' % (idx, line))

            self.assertStatementLine(stmt.lines[0],
                                     amount=Decimal('-500.00'),
                                     payee='VIR M PERPIGNAN ET MME',
                                     memo='Virement vers Compte Cheques',
                                     date=dt(parser, "2023-01-12"),
                                     check_no='4196250')
            self.assertStatementLine(stmt.lines[1],
                                     amount=Decimal('500.00'),
                                     check_no='0812417',
                                     date=datetime(2023, 1, 30, 0, 0),
                                     memo='remboursement de janvier',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[2],
                                     amount=Decimal('-2264.40'),
                                     check_no='6416777',
                                     date=datetime(2023, 3, 12, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[3],
                                     amount=Decimal('1000.00'),
                                     check_no='0812417',
                                     date=datetime(2023, 4, 24, 0, 0),
                                     memo='Virement vers Epargne Casden Pp',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[4],
                                     amount=Decimal('-1000.00'),
                                     check_no='8227408',
                                     date=datetime(2023, 4, 30, 0, 0),
                                     memo='Virement vers COMPTE CHEQUES',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[5],
                                     amount=Decimal('1000.00'),
                                     check_no='0812417',
                                     date=datetime(2023, 5, 9, 0, 0),
                                     memo='Virement vers Epargne Casden Pp',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[6],
                                     amount=Decimal('-1000.00'),
                                     check_no='9168818',
                                     date=datetime(2023, 5, 26, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[7],
                                     amount=Decimal('-1000.00'),
                                     check_no='9210693',
                                     date=datetime(2023, 5, 26, 0, 0),
                                     memo='Virement vers Compte Cheques #2',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[8],
                                     amount=Decimal('1000.00'),
                                     check_no='0812417',
                                     date=datetime(2023, 5, 30, 0, 0),
                                     memo='Virement vers Epargne Casden Pp',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[9],
                                     amount=Decimal('2000.00'),
                                     check_no='0812417',
                                     date=datetime(2023, 6, 1, 0, 0),
                                     memo='Virement vers Epargne Casden Pp',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[10],
                                     amount=Decimal('-3000.00'),
                                     check_no='1707671',
                                     date=datetime(2023, 7, 28, 0, 0),
                                     memo='Virement vers COMPTE CHEQUES',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[11],
                                     amount=Decimal('-2500.00'),
                                     check_no='2094010',
                                     date=datetime(2023, 8, 5, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[12],
                                     amount=Decimal('-100.00'),
                                     check_no='2955098',
                                     date=datetime(2023, 8, 31, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[13],
                                     amount=Decimal('-50.00'),
                                     check_no='2955125',
                                     date=datetime(2023, 8, 31, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN ET MME')
            self.assertStatementLine(stmt.lines[14],
                                     amount=Decimal('-25.00'),
                                     check_no='2955152',
                                     date=datetime(2023, 8, 31, 0, 0),
                                     memo='Virement vers Compte Cheques',
                                     payee='VIR M PERPIGNAN ET MME')
        except Exception as e:
            _, _, tb = sys.exc_info()
            traceback.print_tb(tb)  # Fixed format
            tb_info = traceback.extract_tb(tb)
            filename, line, func, text = tb_info[-1]
            logger.error('Error line {}; statement "{}"'.format(line, text))
            raise e
