# -*- coding: utf-8 -*-
import sys
import re
import io
from decimal import Decimal
from datetime import datetime as dt
import datetime
from subprocess import check_output, CalledProcessError
import logging

from ofxstatement import plugin, parser
from ofxstatement.statement import StatementLine
from ofxstatement.statement import generate_unique_transaction_id

# Need Python 3 for super() syntax
assert sys.version_info[0] >= 3, "At least Python 3 is required."

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Plugin(plugin.Plugin):
    """BanquePopulaire, France, PDF (https://www.banquepopulaire.fr/)
    """

    def get_file_object_parser(self, fh):
        return Parser(fh)

    def get_parser(self, filename):
        pdftotext = ["pdftotext", "-layout", '-enc', 'UTF-8', filename, '-']
        fh = None

        # Is it a PDF or an already converted file?
        try:
            fh = io.StringIO(check_output(pdftotext).decode())
            # No exception: apparently it is a PDF.
        except CalledProcessError:
            fh = open(filename, "r", encoding='UTF-8')

        return self.get_file_object_parser(fh)


class Parser(parser.StatementParser):
    def __init__(self, fin):
        super().__init__()
        self.fin = fin
        self.unique_id_set = set()
        self.bank_id = None
        self.account_id = None
        self.start_balance = None
        self.start_date = None
        self.end_balance = None
        self.end_date = None

    def parse(self):
        """Main entry point for parsers

        super() implementation will call to split_records and parse_record to
        process the file.
        """
        # Python 3 needed
        stmt = super().parse()

        stmt.currency = 'EUR'
        stmt.bank_id = self.bank_id
        stmt.account_id = self.account_id
        stmt.start_balance = self.start_balance
        stmt.start_date = self.start_date
        stmt.end_balance = self.end_balance
        stmt.end_date = self.end_date
        stmt.end_date += datetime.timedelta(days=1)  # exclusive for OFX

        logger.debug('Statement: %r', stmt)

        return stmt

    def split_records(self):
        """Return iterable object consisting of a line per transaction
        """
        def convert_str_to_list(str, max_items=None, sep=r'\s\s+|\t|\n'):
            return [x for x in re.split(sep, str)[0:max_items]]

        def get_amount(amount_in, transaction_type_in):
            sign_out, amount_out = 1, None

            # determine sign_out
            assert isinstance(transaction_type_in, str)
            assert transaction_type_in in ['D', 'C']

            if transaction_type_in == 'D':
                sign_out = -1

            # determine amount_out
            assert isinstance(amount_in, str)
            # Amount may be something like 1 827,97
            m = re.search(r'^([ ,0-9]+)$', amount_in)
            assert m is not None
            amount_out = m.group(1)
            if amount_out[-3] == ',':
                amount_out = amount_out.replace(' ', '').replace(',', '.')

            # convert to str to keep just the last two decimals
            amount_out = Decimal(str(amount_out))

            return sign_out * amount_out

        account_id_pattern = re.compile(r'VOTRE COMPTE CHEQUES N° (\d+)')
        bank_id_pattern = re.compile(r'IBAN\s+(\S.+\S)\s+BIC\s+(\S+)$')
        header_rows = [['DATE',
                        'DATE',
                        'DATE',
                        'DEBIT',
                        'CREDIT'],
                       ['COMPTA'],
                       ['LIBELLE/REFERENCE',
                        'OPERATION VALEUR',
                        'EUROS',
                        'EUROS']]
        accounting_date_pos = None  # DATE COMPTA
        description_pos = None  # LIBELLE/REFERENCE
        operation_date_pos = None  # DATE OPERATION
        value_date_pos = None  # DATE VALEUR
        debit_pos = None
        credit_pos = None

        balance_pattern = \
            re.compile(r'SOLDE CREDITEUR AU (../../....).\s+([ ,0-9]+)$')
        transaction_pattern = \
            re.compile(r'\s+\S.*\S\s+\d\d/\d\d\s+\d\d/\d\d\s+[ ,0-9]+$')

        read_end_balance_line = False

        stmt_line = None

        # breakpoint()
        for line in self.fin:
            logger.debug('line: %s', line)

            pos = line.lstrip().find('TOTAL DES MOUVEMENTS')
            logger.debug('pos: %d', pos)

            if pos == 0:
                read_end_balance_line = True
                continue

            if not self.account_id:
                m = account_id_pattern.search(line)
                if m:
                    self.account_id = m.group(1)
                    logger.debug('account_id: %s', self.account_id)
                continue

            if not self.bank_id:
                m = bank_id_pattern.search(line)
                if m:
                    self.bank_id = m.group(2)
                    logger.debug('bank_id: %s', self.bank_id)
                continue

            assert self.account_id and self.bank_id

            m = balance_pattern.search(line)
            if m:
                logger.debug('date: %s; balance: %s', m.group(1), m.group(2))
                date = dt.strptime(m.group(1), '%d/%m/%Y').date()
                balance = m.group(2)
                transaction_type = \
                    'C' if line.rfind(balance) >= credit_pos else 'D'
                if read_end_balance_line:
                    self.end_balance = get_amount(balance, transaction_type)
                    self.end_date = date
                    break
                elif not(self.start_balance and self.start_date):
                    self.start_balance = get_amount(balance, transaction_type)
                    self.start_date = date
                continue

            row = convert_str_to_list(line.strip())
            logger.debug('row: %s', str(row))
            if row == header_rows[0]:
                    debit_pos = line.find('DEBIT')
                    assert debit_pos >= 0
                    credit_pos = line.find('CREDIT')
                    assert credit_pos >= 0
            elif row == header_rows[1]:
                    accounting_date_pos = line.find('COMPTA')
                    assert accounting_date_pos >= 0
            elif row == header_rows[2]:
                    description_pos = line.find('LIBELLE/REFERENCE')
                    assert description_pos >= 0
                    operation_date_pos = line.find('OPERATION')
                    assert operation_date_pos >= 0
                    value_date_pos = line.find('VALEUR')
                    assert value_date_pos >= 0
            else:
                m = transaction_pattern.search(line)
                if m:
                    assert debit_pos >= 0
                    assert credit_pos >= 0
                    assert accounting_date_pos >= 0
                    assert description_pos >= 0
                    assert value_date_pos >= 0

                    if stmt_line is not None:
                        yield stmt_line
                    stmt_line = StatementLine()
                    stmt_line.check_no = row[-4] if len(row) >= 6 else None
                    stmt_line.date = row[-3]
                    stmt_line.amount = row[-1]
                    transaction_type = \
                        'C' if line.rfind(row[-1]) >= credit_pos else 'D'

                    # Should have 6 columns. If not: reduce.
                    while len(row) > 6:
                        row[2] += ' ' + row[3]
                        del row[3]

                    stmt_line.payee = row[2]
                    stmt_line.memo = ''
                    stmt_line.amount = get_amount(stmt_line.amount,
                                                  transaction_type)
                elif stmt_line is not None:
                    # Continuation of a transaction?
                    pos = line.find(line.lstrip())
                    if pos > accounting_date_pos and pos < operation_date_pos:
                        stmt_line.memo += " " + line.strip()
                    elif line.strip() != '':
                        # not part of a transaction
                        yield stmt_line
                        stmt_line = None

        # end of while loop
        if stmt_line is not None:
            yield stmt_line

    def parse_record(self, stmt_line):
        """Parse given transaction line and return StatementLine object
        """
        def add_years(d, years):
            """Return a date that's `years` years after the date (or datetime)
            object `d`. Return the same calendar date (month and day) in the
            destination year, if it exists, otherwise use the following day
            (thus changing February 29 to March 1).

            """
            return d.replace(year=d.year + years, month=3, day=1) \
                if d.month == 2 and d.day == 29 \
                else d.replace(year=d.year + years)

        def get_date(s: str):
            d = dt.strptime(s, '%d/%m').date()
            # Without a year it will be 1900 so augment
            while d < self.start_date:
                d = add_years(d, 1)
            return d

        logger.debug('Statement line: %r', stmt_line)

        # Remove zero-value notifications
        if stmt_line.amount == 0:
            return None

        stmt_line.date = get_date(stmt_line.date)

        stmt_line.id = \
            generate_unique_transaction_id(stmt_line, self.unique_id_set)
        m = re.search(r'-(\d+)$', stmt_line.id)
        if m:
            counter = int(m.group(1))
            # include counter so the memo gets unique
            stmt_line.memo = stmt_line.memo + ' #' + str(counter + 1)

        return stmt_line
