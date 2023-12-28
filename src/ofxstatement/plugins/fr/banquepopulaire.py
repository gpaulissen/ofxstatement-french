# -*- coding: utf-8 -*-
from typing import Iterable, Optional, List, Iterator
from typing import Pattern, Match, cast, Union

import sys
import re
import io
import os
from decimal import Decimal
from datetime import date, datetime, timedelta
from subprocess import check_output, CalledProcessError
import logging

from ofxstatement.plugin import Plugin as BasePlugin
from ofxstatement.parser import StatementParser as BaseStatementParser
from ofxstatement.statement import Statement as BaseStatement
from ofxstatement.statement import StatementLine as BaseStatementLine
from ofxstatement.statement import generate_unique_transaction_id

from ofxstatement.plugins.fr.statement import Statement, StatementLine
from ofxstatement.plugins.fr.statement import StatementCache


# Need Python 3 for super() syntax
assert sys.version_info[0] >= 3, "At least Python 3 is required."

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Parser(BaseStatementParser[BaseStatementLine]):
    statement: Statement
    fin: Iterable[str]
    statement_cache: StatementCache
    bank_id: Optional[str]

    def __init__(self,
                 fin: Iterable[str],
                 ofx_files: Optional[str] = None,
                 cwd: Optional[str] = None,
                 bank_id: Optional[str] = None):
        super().__init__()
        self.statement = Statement()  # My Statement()
        self.fin = fin
        self.statement_cache = StatementCache(ofx_files, cwd)
        self.bank_id = bank_id

    def parse(self) -> BaseStatement:
        """Main entry point for parsers

        super() implementation will call to split_records and parse_record to
        process the file.
        """

        self.statement_cache.read()

        stmt: Statement = Statement.copy_from_base(super().parse())

        stmt.currency = 'EUR'
        if stmt.end_date:
            stmt.end_date += timedelta(days=1)  # exclusive for OFX

        logger.debug('Statement: %r', stmt)

        return stmt

    def split_records(self) -> Iterator[BaseStatementLine]:
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

        III) The DATE COMPTA is used as the date field.

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

        VI) Or what do you think of these two transactions?

       Example 1:

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
        pdftotext. The image is converted into an empty line and an F followed
        by whitespace above (!) the rest of the current memo.

        Example 2:

 26/09|F COTIS AFFINEA
      |XCCNV999 2019092500010929000001
      |                                   0010929|25/09    |25/09|7,18  |

      |F COTIS AFFINEA
      |CONTRAT CNV0004207796
 26/09|                                   0010930|25/09    |25/09|12,18 |
      |XCCNV999 2019092500010930000001
      |CONTRAT CNV0004207797

        which should be actually:

 26/09|COTIS AFFINEA                      0010929|25/09    |25/09|7,18  |
      |XCCNV999 2019092500010929000001
      |CONTRAT CNV0004207796

 26/09|COTIS AFFINEA                      0010930|25/09    |25/09|12,18 |
      |XCCNV999 2019092500010930000001
      |CONTRAT CNV0004207797

        This should be solved by matching a transaction over this line
        and the second line after that, a lookahead.

        VII) In this case the second part (DEBIT DIFFERE) off the description
        line is not a check number but just part of the name. There is a
        bandwith for the check number. Some heuristics show that the start
        of the reference number + 19 is at least the position of the operation
        date column. Let's make 20 the threshold.

 28/06|CARTE     DEBIT DIFFERE                    |28/06    |30/06 |6,70 |


        """
        def convert_str_to_list(str: str,
                                max_items: Optional[int] = None,
                                sep: str = r'\s\s+|\t|\n') -> List[str]:
            return [x for x in re.split(sep, str)[0:max_items]]

        def get_debit_credit(line: str, amount: str, credit_pos: int) -> str:
            return 'C' if line.rfind(amount) >= credit_pos else 'D'

        def get_amount(amount_in: Decimal,
                       transaction_type_in: str) -> Decimal:
            sign_out: int = 1
            amount_out: Optional[Decimal] = None

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

        F_pattern: Pattern[str] = re.compile(r'(F\s+)')
        account_id_pattern: Pattern[str] = re.compile(r'VOTRE .* N° (\d+)')
        bank_id_pattern: Pattern[str]
        bank_id_pattern = re.compile(r'IBAN\s+(\S.+\S)\s+BIC\s+(\S+)')
        # The first header row should appear like that but the second
        # is spread out over two lines.
        header_rows: List[List[str]] = [['DATE',
                                         'DATE',
                                         'DATE',
                                         'DEBIT',
                                         'CREDIT'],
                                        ['COMPTA',
                                         'LIBELLE/REFERENCE',
                                         'OPERATION',
                                         'VALEUR',
                                         'EUROS',
                                         'EUROS']]
        second_header_row: List[str] = []
        accounting_date_pos: Optional[int] = None  # DATE COMPTA
        description_pos: Optional[int] = None  # LIBELLE/REFERENCE
        operation_date_pos: Optional[int] = None  # DATE OPERATION
        value_date_pos: Optional[int] = None  # DATE VALEUR
        debit_pos: Optional[int] = None
        credit_pos: Optional[int] = None
        # 20 before DATE OPERATION (guessed, see note VII)
        check_no_pos: Optional[int] = None

        balance_pattern: Pattern[str] = \
            re.compile(r'SOLDE (CRED|DEB)ITEUR AU (../../....).\s+([ ,0-9]+)$')
        transaction_pattern: Pattern[str] = \
            re.compile(r'\d\d/\d\d\s+\S.*\s+\d\d/\d\d\s+\d\d/\d\d\s+[ ,0-9]+$')

        read_end_balance_line: bool = False

        stmt_line: Optional[StatementLine] = None
        stmt_lines: List[StatementLine] = []
        payee: Optional[str] = None  # to handle note VI

        # Need to be able to loook ahead for complicated cases
        lines: List[str] = [line for line in self.fin]

        pos: int
        m: Optional[Match[str]]
        transaction_type: str
        line_stripped: str
        accounting_date: date
        balance: Union[str, Decimal]
        row: List[str]
        combined_line: str

        # breakpoint()
        for idx, line in enumerate(lines, start=1):
            line_stripped = line.strip()
            if line_stripped != '':
                logger.debug('line %04d: %s', idx, line)

                pos = line_stripped.find('TOTAL DES MOUVEMENTS')

                if pos == 0:  # found
                    read_end_balance_line = True
                    continue

            if not self.statement.account_id:
                m = account_id_pattern.match(line_stripped)
                if m:
                    self.statement.account_id = m.group(1)
                    self.statement_cache.set_unique_id_set(self.statement.account_id, set())  # nopep8
                    logger.debug('account_id: %s', self.statement.account_id)
                continue

            if not self.statement.bank_id:
                m = bank_id_pattern.match(line_stripped)
                if m:
                    self.statement.bank_id = m.group(2)
                    logger.debug('bank_id: %s', self.statement.bank_id)
                elif self.bank_id:
                    self.statement.bank_id = self.bank_id
                    logger.debug('bank_id: %s', self.statement.bank_id)
                continue

            assert self.statement.account_id and self.statement.bank_id

            m = balance_pattern.match(line_stripped)
            if m:
                accounting_date = datetime.strptime(m.group(2),
                                                    '%d/%m/%Y').date()
                balance = m.group(3)
                logger.debug('accounting_date: %s; balance: %s',
                             accounting_date,
                             balance)
                assert credit_pos is not None
                transaction_type = get_debit_credit(line, balance, credit_pos)
                balance = cast(Decimal, balance)
                if read_end_balance_line:
                    self.statement.end_balance = get_amount(balance,
                                                            transaction_type)
                    self.statement.end_date = \
                        datetime.combine(accounting_date,
                                         datetime.min.time())
                    break
                elif self.statement.start_balance is None:
                    self.statement.start_balance = get_amount(balance,
                                                              transaction_type)
                    self.statement.start_date = \
                        datetime.combine(accounting_date,
                                         datetime.min.time())
                continue

            row = convert_str_to_list(line_stripped)

            if row == header_rows[0]:
                logger.debug('header row 1: %s', str(row))
                debit_pos = line.find('DEBIT')
                assert debit_pos >= 0
                credit_pos = line.find('CREDIT')
                assert credit_pos >= 0
                # Create a copy
                second_header_row = header_rows[1][:]
                logger.debug('second header row: %s', str(second_header_row))
                continue
            elif second_header_row:
                row = convert_str_to_list(line_stripped, sep=r'\s+|\t|\n')
                logger.debug('header row 2/3: %s', str(row))
                # Are the columns of this row a subset of header_rows[1]?
                if set(row) < set(header_rows[1]):
                    for col in row:
                        if col == 'COMPTA':
                            accounting_date_pos = line.find(col)
                            assert accounting_date_pos >= 0
                        elif col == 'LIBELLE/REFERENCE':
                            description_pos = line.find(col)
                            assert description_pos >= 0
                        elif col == 'OPERATION':
                            operation_date_pos = line.find(col)
                            assert operation_date_pos >= 0
                            check_no_pos = operation_date_pos - 20
                            assert check_no_pos >= 0
                        elif col == 'VALEUR':
                            value_date_pos = line.find(col)
                            assert value_date_pos >= 0
                        elif col == 'EUROS':
                            pass
                        second_header_row.remove(col)
                logger.debug('second header row: %s', str(second_header_row))
                continue
            elif len(row[0]) > 0:
                logger.debug('row: %s', str(row))

            # Empty line
            if len(row) == 1 and row[0] == '':
                if payee is None:
                    # Note VI: first, empty line
                    payee = ''
                elif payee != '':  # pragma: no cover
                    # Obviously an empty line after an F\s+ line
                    payee = None
                else:
                    pass  # several empty lines before an F line possible
                logger.debug('payee: %s', payee)
                continue
            # Handle note VI
            elif payee == '' and len(row) == 1 and F_pattern.match(row[0]):
                # Note VI: second line left trimmed starting with F
                payee = row[0][2:]
                logger.debug('payee: %s', payee)
                continue
            else:
                logger.debug('payee: %s', payee)

            m = transaction_pattern.match(line_stripped)

            # See note VI, example 2
            if not m and\
               idx + 2 <= len(lines) and\
               len(row) >= 2 and\
               (F_pattern.match(row[1]) or (len(row) >= 3 and row[1] == 'F')):
                assert line == lines[idx - 1]
                # The first line right stripped and the 'F\s+' replaced by ''
                combined_line = lines[idx - 1].rstrip()
                m = F_pattern.search(combined_line)
                assert m
                combined_line = combined_line.replace(m.group(1), '')
                # Add the second line (two rows further) from the point
                # where the first right trimmed line ends, but only if
                # the part before that point contains just whitespace.
                if lines[idx - 1 + 2][0:len(combined_line)].strip() == '':
                    combined_line += lines[idx - 1 + 2][len(combined_line):]
                    logger.debug('combined line stripped: %s',
                                 combined_line.strip())
                    m = transaction_pattern.match(combined_line.strip())
                    if m:
                        del lines[idx - 1 + 2]  # not necessary anymore
                        # recalculate some helper variables
                        line = combined_line
                        line_stripped = line.strip()
                        row = convert_str_to_list(line_stripped)

            if m:
                logger.debug('found a transaction line')

                assert debit_pos is not None and debit_pos >= 0
                assert credit_pos is not None and credit_pos >= 0
                assert accounting_date_pos is not None \
                    and accounting_date_pos >= 0
                assert description_pos is not None and description_pos >= 0
                assert value_date_pos is not None and value_date_pos >= 0

                # emit previous transaction if any
                if stmt_line is not None:
                    stmt_lines.append(stmt_line)
                    stmt_line = None

                # Note VI
                if payee is not None and payee != '':
                    row.insert(1, payee)
                    payee = None
                    logger.debug('After adding payee to the row: %s', str(row))

                check_no: Optional[str] = None
                if len(row) >= 6:
                    pos = line.find(row[-4])
                    assert check_no_pos is not None
                    if pos >= check_no_pos:
                        check_no = row[-4]
                        logger.debug('Setting check_no: %s', row[-4])
                    else:
                        logger.debug('Skip setting check_no')

                stmt_line = StatementLine(check_no,
                                          cast(Decimal, row[-1]),
                                          row[0],
                                          row[-2],
                                          row[-3])

                assert credit_pos is not None
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
                assert stmt_line.amount is not None
                stmt_line.amount = get_amount(stmt_line.amount,
                                              transaction_type)
                logger.debug('Statement line: %r', stmt_line)
            elif stmt_line is not None:
                assert accounting_date_pos is not None
                assert operation_date_pos is not None
                # Continuation of a transaction?
                # Or stated otherwise does the memo text completely fit
                # in the second column?
                pos = line.find(line_stripped)
                if pos > accounting_date_pos and\
                   pos + len(line_stripped) < operation_date_pos:
                    if stmt_line.memo == '':
                        stmt_line.memo = line_stripped
                    elif stmt_line.memo:
                        stmt_line.memo += " " + line_stripped

        # end of while loop
        # assert self.statement.account_id, "No account id found."
        # assert self.statement.bank_id, "No bank id found."
        # assert stmt_lines, "No statement lines found."
        if stmt_line is not None:
            stmt_lines.append(stmt_line)
        # We can only yield the statement lines when end_date is there,
        # see function get_date() below
        return (sl for sl in stmt_lines)

    def parse_record(self, line: BaseStatementLine) -> Optional[BaseStatementLine]:  # nopep8
        """Parse given transaction line and return BaseStatementLine object
        """

        logger.debug('Statement line: %r', line)

        # Remove zero-value notifications
        if line.amount == 0:  # pragma: no cover
            return None

        assert self.statement.end_date
        # Convert the parent class instance to a child class instance
        line = StatementLine.copy_from_base(line)

        line.end_date = self.statement.end_date
        line.adjust(self.statement_cache, str(self.statement.account_id))
        if not line.id and self.statement.account_id is not None:
            line.date = datetime.combine(line.accounting_date,
                                         datetime.min.time())
            account_id = self.statement.account_id
            line.id = \
                generate_unique_transaction_id(line,
                                               self.statement_cache.get_unique_id_set(account_id))  # nopep8
            m = re.match(r'([0-9a-f]+)(-\d+)?$', line.id)
            assert m, "Id should match hexadecimal digits, \
optionally followed by a minus and a counter: '{}'".format(line.id)
            if m.group(2):
                counter = int(m.group(2)[1:])
                # include counter so the memo gets unique
                if line.memo:
                    line.memo = line.memo + ' #' + str(counter + 1)

        return line


class Plugin(BasePlugin):
    """BanquePopulaire, France, PDF (https://www.banquepopulaire.fr/)
    """

    def get_file_object_parser(self,
                               fh: Iterable[str],
                               ofx_files: Optional[str] = None,
                               cwd: Optional[str] = None,
                               bank_id: Optional[str] = None) -> Parser:
        return Parser(fh, ofx_files, cwd, bank_id)

    def get_parser(self, filename: str) -> Parser:
        pdftotext: List[str] = ["pdftotext",
                                "-layout",
                                '-enc',
                                'UTF-8',
                                filename,
                                '-']
        fh: Iterable[str]
        ofx_files: Optional[str]
        bank_id: Optional[str]

        # Is it a PDF or an already converted file?
        try:
            fh = io.StringIO(check_output(pdftotext).decode())
            # No exception: apparently it is a PDF.
        except CalledProcessError:
            fh = open(filename, "r", encoding='UTF-8')

        try:
            ofx_files = self.settings['ofx_files']
        except Exception:
            ofx_files = None

        # Use the directory of the filename as the working directory
        cwd: str = os.path.dirname(os.path.realpath(filename))

        try:
            bank_id = self.settings['bank_id']
        except Exception:
            bank_id = None

        return self.get_file_object_parser(fh, ofx_files, cwd, bank_id)
