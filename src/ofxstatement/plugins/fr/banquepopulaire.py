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
        """Return iterable object consisting of a line per transaction.

        It starts by determining in order):
        A) the account id
        B) the BIC of the bank
        C) the transactions that have 6 columns

        The 6 columns (spread over 3 rows) of the transactions:
        1) DATE COMPTA
        2) LIBELLE/REFERENCE
        3) DATE OPERATION
        4) DATE VALEUR
        5) DEBIT EUROS
        6) CREDIT EUROS

        Notes about parsing
        ===================
        I) The difficulty with the transactions is that the amount has not a
        sign so you have to know the position on the line whether it is debit
        or credit, see also function get_debit_credit.

        II) The description column on the first line contains on the left the
        name (payee) and on the right a check number. Lines 2 and so on
        determine the memo field.

        III) The DATE OPERATION is used as the date field.

        IV) Amounts follow the french format: a space as the thousands
        separator and a comma as the decimal separator.

        V) A transaction may be spread over several lines like this (columns
        left trimmed and separated by a bar):

DATE  |                                          |DATE     |DATE  |DEBIT|CREDIT
COMPTA|                                          |
      |LIBELLE/REFERENCE                         |OPERATION|VALEUR|EUROS|EUROS
======|==========================================|=========|======|=====|======
 20/06|PRLV SEPA AUTOROUTES DU            YYYYYYY|20/06    |20/06 |43,70|
      |XXXXXXXXXXXXXXXXXXXX XXXXXX
      |YYYYYYYYYYYYYYYYYYY

        III) Or what do you think of these two transactions?

 13/06|PRLV SEPA AVANSSUR                 ZZZZZZZ|13/06    |13/06 |     |30,99
      |Direct Assurance 999999999

      |F FRAIS/VIREMENT
      |AAAAAAAAAAA
 13/06|                                   BBBBBBB|13/06    |13/06 |     |4,10
      |00001 OPERATION

        Which are actually:

 13/06|PRLV SEPA AVANSSUR                 ZZZZZZZ|13/06    |13/06 |     |30,99
      |Direct Assurance 999999999
      |AAAAAAAAAAA
 13/06|FRAIS/VIREMENT                     BBBBBBB|13/06    |13/06 |     |4,10
      |00001 OPERATION

        But due to an image in the PDF the lines are spread out wrongly by
        pdftotext. The image is converted into an empty line and an 'F '
        above (!) the rest of the current memo.

        VI) In this case the second part (DEBIT DIFFERE) off the description
        line is not a check number but just part of the name. There is a
        bandwith for the check number. Some heuristics show that the start
        of the reference number + 19 is at least the position of the operation
        date column. Let's make 20 the threshold.

 28/06|CARTE     DEBIT DIFFERE                    |28/06    |30/06 |6,70 |


        """
        def convert_str_to_list(str, max_items=None, sep=r'\s\s+|\t|\n'):
            return [x for x in re.split(sep, str)[0:max_items]]

        def get_debit_credit(line: str, amount: str, credit_pos: int):
            return 'C' if line.rfind(amount) >= credit_pos else 'D'

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
        check_no_pos = None  # 20 before DATE OPERATION (guessed, see note VI)

        balance_pattern = \
            re.compile(r'SOLDE CREDITEUR AU (../../....).\s+([ ,0-9]+)$')
        transaction_pattern = \
            re.compile(r'\d\d/\d\d\s+\S.*\s+\d\d/\d\d\s+\d\d/\d\d\s+[ ,0-9]+$')

        read_end_balance_line = False

        stmt_line = None
        payee = None  # to handle note V

        # breakpoint()
        for idx, line in enumerate(self.fin, start=1):
            line_stripped = line.strip()
            if line_stripped != '':
                logger.debug('line %04d: %s', idx, line)

                pos = line_stripped.find('TOTAL DES MOUVEMENTS')

                if pos == 0:  # found
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
                transaction_type = get_debit_credit(line, balance, credit_pos)
                if read_end_balance_line:
                    self.end_balance = get_amount(balance, transaction_type)
                    self.end_date = date
                    break
                elif not(self.start_balance and self.start_date):
                    self.start_balance = get_amount(balance, transaction_type)
                    self.start_date = date
                continue

            row = convert_str_to_list(line_stripped)
            if len(row[0]) > 0:
                logger.debug('row: %s', str(row))

            if row in header_rows:
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
                    check_no_pos = operation_date_pos - 20
                    assert check_no_pos >= 0
                    value_date_pos = line.find('VALEUR')
                    assert value_date_pos >= 0
                continue

            # Empty line
            if len(row) == 1 and row[0] == '':
                if payee is None:
                    # Note V: first, empty line
                    payee = ''
                elif payee != '':  # pragma: no cover
                    # Obviously an empty line after an 'F ' line
                    payee = None
                else:
                    pass  # several empty lines before an 'F ' line possible
                logger.debug('payee: %s', payee)
                continue
            # Handle note V
            elif payee == '' and len(row) == 1 and row[0][0:2] == 'F ':
                # Note V: second line left trimmed starting with 'F '
                payee = row[0][2:]
                logger.debug('payee: %s', payee)
                continue
            else:
                logger.debug('payee: %s', payee)

            m = transaction_pattern.search(line)
            if m:
                logger.debug('found a transaction line')

                assert debit_pos >= 0
                assert credit_pos >= 0
                assert accounting_date_pos >= 0
                assert description_pos >= 0
                assert value_date_pos >= 0

                # emit previous transaction if any
                if stmt_line is not None:
                    yield stmt_line
                    stmt_line = None

                # Note 5
                if payee is not None and payee != '':
                    row.insert(1, payee)
                    payee = None
                    logger.debug('After adding payee to the row: %s', str(row))

                stmt_line = StatementLine()
                if len(row) >= 6 and line.find(row[-4]) >= check_no_pos:
                    stmt_line.check_no = row[-4]
                    logger.debug('Setting check_no: %s', row[-4])

                stmt_line.date = row[-3]
                stmt_line.amount = row[-1]
                transaction_type = \
                    get_debit_credit(line, row[-1], credit_pos)

                # Should have 6 columns. If not: reduce.
                if len(row) > 6:  # pragma: no cover
                    while len(row) > 6:
                        row[2] += ' ' + row[3]
                        del row[3]
                    logger.debug('row after reducing columns: %s', str(row))

                stmt_line.payee = row[1]
                stmt_line.memo = ''
                stmt_line.amount = get_amount(stmt_line.amount,
                                              transaction_type)
                logger.debug('Statement line: %r', stmt_line)
            elif stmt_line is not None:
                # Continuation of a transaction?
                # Or stated otherwise does the memo text completely fit
                # in the second column?
                pos = line.find(line_stripped)
                if pos > accounting_date_pos and\
                   pos + len(line_stripped) < operation_date_pos:
                    if stmt_line.memo == '':
                        stmt_line.memo = line_stripped
                    else:
                        stmt_line.memo += " " + line_stripped

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
        if stmt_line.amount == 0:  # pragma: no cover
            return None

        stmt_line.date = get_date(stmt_line.date)

        stmt_line.id = \
            generate_unique_transaction_id(stmt_line, self.unique_id_set)
        m = re.search(r'-(\d+)$', stmt_line.id)
        if m:  # pragma: no cover
            counter = int(m.group(1))
            # include counter so the memo gets unique
            stmt_line.memo = stmt_line.memo + ' #' + str(counter + 1)

        return stmt_line
