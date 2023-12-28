# -*- coding: utf-8 -*-

from typing import Optional, Iterator, Any, Dict, NamedTuple, Set

import sys
import os
import glob

from datetime import date, datetime
from decimal import Decimal
from contextlib import contextmanager

from bs4 import BeautifulSoup

from ofxstatement.statement import Statement as BaseStatement
from ofxstatement.statement import StatementLine as BaseStatementLine
from ofxstatement.exceptions import ValidationError

import logging

# Need Python 3 for super() syntax
assert sys.version_info[0] >= 3, "At least Python 3 is required."

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Statement(BaseStatement):
    def __init__(self) -> None:
        super().__init__()

    # forward reference as a string
    @staticmethod
    def copy_from_base(parent: BaseStatement) -> 'Statement':
        obj: Statement = Statement()
        obj.__dict__.update(parent.__dict__)  # copy values from parent
        return obj

    def assert_valid(self) -> None:
        try:
            super().assert_valid()
            assert self.end_date, "The statement end date should be set"
            dates = [StatementLine.copy_from_base(sl).accounting_date
                     for sl in self.lines]
            min_date: date = min(dates)
            max_date: date = max(dates)
            start_date: Optional[date] = \
                self.start_date.date() if self.start_date else None
            end_date: Optional[date] = \
                self.end_date.date() if self.end_date else None
            assert start_date is None or start_date <= min_date, \
                "The statement start date ({}) should at most the smallest \
statement line date ({})".format(start_date, min_date)
            assert end_date is None or end_date > max_date, \
                "The statement end date ({}) should be greater than the \
largest statement line date ({})".format(end_date, max_date)
        except Exception as e:
            raise ValidationError(str(e), self)


class StatementLine(BaseStatementLine):
    def __init__(self,
                 check_no: Optional[str] = None,
                 amount: Optional[Decimal] = None,
                 accounting_date_d_m: Optional[str] = None,
                 operation_date_d_m: Optional[str] = None,
                 value_date_d_m: Optional[str] = None,
                 end_date: Optional[datetime] = None) -> None:
        super().__init__()
        self.check_no = check_no
        self.amount = amount
        self.accounting_date_d_m: Optional[str] = accounting_date_d_m
        self.operation_date_d_m: Optional[str] = operation_date_d_m
        self.value_date_d_m: Optional[str] = value_date_d_m
        self.end_date: Optional[datetime] = end_date

    # forward reference as a string
    @staticmethod
    def copy_from_base(parent: BaseStatementLine) -> 'StatementLine':
        obj: StatementLine = StatementLine()
        obj.__dict__.update(parent.__dict__)  # copy values from parent
        return obj

    def get_date(self, d_m: str) -> date:
        def add_years(d: date, years: int) -> date:
            """Return a date that's `years` years after the date
            object `d`. Return the same calendar date (month and day) in the
            destination year, if it exists, otherwise use the following day
            (thus changing February 29 to March 1).
            """
            return d.replace(year=d.year + years, month=3, day=1) \
                if d.month == 2 and d.day == 29 \
                else d.replace(year=d.year + years)

        assert self.end_date
        # Without a year it will be 1900 so add the year
        d_m_y: str = "{}/{}".format(d_m, self.end_date.year)
        d: date = datetime.strptime(d_m_y, '%d/%m/%Y').date()
        if d > self.end_date.date():
            d = add_years(d, -1)
        assert d <= self.end_date.date()
        return d

    @property
    def accounting_date(self) -> date:
        assert self.accounting_date_d_m is not None
        return self.get_date(self.accounting_date_d_m)

    @property
    def operation_date(self) -> date:
        assert self.operation_date_d_m is not None
        return self.get_date(self.operation_date_d_m)

    @property
    def value_date(self) -> date:
        assert self.value_date_d_m is not None
        return self.get_date(self.value_date_d_m)


@contextmanager
def working_directory(path: str) -> Iterator[Any]:
    """
    A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.
    Usage:
    > # Do something in original directory
    > with working_directory('/my/new/path'):
    >     # Do something in new directory
    > # Back to old directory
    """
    prev_cwd: str = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


class TransactionKey(NamedTuple):
    """
    This OFX transaction:

    <STMTTRN>
    <TRNTYPE>CREDIT
    <DTPOSTED>20191126
    <TRNAMT>+248.21
    <FITID>201901100044BD27
    <CHECKNUM>F6KJAIV
    <NAME>EVI DRFIP NOUVELLE AQUIT
    <MEMO>REMUNERATION DU 11/2019. MINISTE RE : 206 GESTION : 991-033
    </STMTTRN>

    will be shown in the PDF as:

    accounting_date: 26/11/2019
    payee: VIREMENT SEPA
    operation_date: 26/11/2019
    value_date: 26/11/2019
    amount: 248,21
    memo: EVI DRFIP NOUVELLE AQUIT
    check_no: -

    So we do not know from the OFX whether it is a VIREMENT SEPA or not and
    therefore we will add two keys:
    1. one with CHECKNUM from the OFX and NAME empty
    2. one with CHECKNUM empty and the NAME from the OFX

    Update 2023-12-27

    Now this case in file tests/samples/BPACA_OP_20220828.ofx:

    <STMTTRN>
    <TRNTYPE>DEBIT
    <DTPOSTED>20220803
    <TRNAMT>-150.00
    <FITID>202200800003BD27
    <CHECKNUM>9W8HMCI
    <NAME>020822 CB****6516
    <MEMO>SNCF INTERNET  75PARIS 10
    </STMTTRN>

    <STMTTRN>
    <TRNTYPE>DEBIT
    <DTPOSTED>20220803
    <TRNAMT>-150.00
    <FITID>202200800004BD27
    <CHECKNUM>9W8HMCJ
    <NAME>020822 CB****6516
    <MEMO>SNCF INTERNET  75PARIS 10
    </STMTTRN>

    This results in an error since the key does not have CHECKNUM:

    Different transaction data found.
    key: TransactionKey(account_id='99999999999', checknum=None, dtposted=datetime.date(2022, 8, 3), trnamt=Decimal('-150.00'), name='020822 CB****6516')  # nopep8
    new: TransactionData(ofx_file='BPACA_OP_20220828.ofx', id='202200800003BD27', name='020822 CB****6516', memo='SNCF INTERNET 75PARIS 10')  # nopep8
    old: TransactionData(ofx_file='BPACA_OP_20220828.ofx', id='202200800004BD27', name='020822 CB****6516', memo='SNCF INTERNET 75PARIS 10')  # nopep8
    differences: {('id', '202200800004BD27'), ('id', '202200800003BD27')}

    So clearly we have to add another case:
    3. one with CHECKNUM and NAME from the OFX

    """
    account_id: str
    checknum: Optional[str]
    dtposted: Optional[date]
    trnamt: Optional[Decimal]
    name: Optional[str]  # for VIREMENT SEPA

    @staticmethod
    def make(account_id: str,
             check_no: Optional[str],
             dtposted: Optional[date],
             amount: Optional[Decimal],
             name: Optional[str]) -> 'TransactionKey':
        assert isinstance(account_id, str), \
            "account_id (%s) must be an instance of str" % (type(account_id))
        assert check_no is None or isinstance(check_no, str), \
            "check_no (%s) must be an instance of str" % (type(check_no))
        assert dtposted is None or isinstance(dtposted, date), \
            "dtposted (%s) must be an instance of date" % (type(dtposted))
        assert amount is None or isinstance(amount, Decimal), \
            "amount (%s) must be an instance of Decimal" % (type(amount))
        assert name is None or isinstance(name, str), \
            "name (%s) must be an instance of str" % (type(name))

        return TransactionKey(account_id,
                              None if check_no == '' else check_no,
                              dtposted,
                              amount,
                              None if name == '' else name)


class TransactionData(NamedTuple):
    ofx_file: str
    id: str
    name: Optional[str]
    memo: Optional[str]

    @staticmethod
    def make(ofx_file: str,
             id: str,
             payee: Optional[str],
             memo: Optional[str]) -> 'TransactionData':
        assert isinstance(ofx_file, str), \
            "ofx_file (%s) must be an instance of str" % (type(ofx_file))
        assert isinstance(id, str), \
            "id (%s) must be an instance of str" % (type(id))
        assert payee is None or isinstance(payee, str), \
            "payee (%s) must be an instance of str or None" % (type(payee))
        assert memo is None or isinstance(memo, str), \
            "memo (%s) must be an instance of str or None" % (type(memo))

        # If payee or memo is not empty there may be a whitespace difference
        # so remove multiple whitespace characters by a single one
        payee = ' '.join(payee.split()) if payee else None
        memo = ' '.join(memo.split()) if memo else None

        return TransactionData(ofx_file,
                               id,
                               None if payee == '' else payee,
                               None if memo == '' else memo)

    @staticmethod
    def merge(src: 'TransactionData',
              dst: 'TransactionData') -> 'TransactionData':
        # prefer id without a space
        if ' ' in src.id and ' ' not in dst.id:
            return TransactionData.merge(dst, src)
        return TransactionData(src.ofx_file,
                               src.id,
                               src.name if src.name is not None else dst.name,
                               src.memo if src.memo is not None else dst.memo)


class StatementCache(object):
    unique_id_sets: Dict[str, Set[str]]
    ofx_files: Optional[str]
    cwd: str
    cache: Dict[TransactionKey, TransactionData]
    printed: bool

    def __init__(self,
                 ofx_files: Optional[str],
                 cwd: Optional[str]) -> None:
        self.unique_id_sets = {}  # per account_id
        self.ofx_files = ofx_files
        self.cwd = cwd if cwd is not None else os.getcwd()
        self.cache = {}
        self.printed = False

    def read(self) -> None:
        """Read the OFX files for their id so they can be used instead of
        generate_unique_transaction_id()
        """
        logger.debug('CWD before working_directory(): %s', os.getcwd())
        if self.ofx_files:
            with working_directory(self.cwd):
                logger.debug('CWD while globbing: %s', os.getcwd())
                for path in self.ofx_files.split(","):
                    ofx_files = set()
                    for ofx_file in glob.glob(path):
                        if ofx_file not in ofx_files:
                            self.process_ofx_file(ofx_file)
                            ofx_files.add(ofx_file)
                    if len(ofx_files) == 0:
                        raise ValidationError(
                            'No OFX file found for path "%s" part of "%s"' %
                            (path, self.ofx_files), self)
        self.print('after read')
        logger.debug('CWD after working_directory(): %s', os.getcwd())

    def process_ofx_file(self, ofx_file: str) -> None:
        """Process an OFX file using Beautiful Soup.
        """
        def tag2text(tag: Any,
                     name_to_find: str) -> Optional[str]:
            found = tag.find(name_to_find)
            return found.contents[0].strip() if found else None

        def tag2date(tag: Any,
                     name_to_find: str,
                     format: str) -> Optional[date]:
            text: Optional[str] = tag2text(tag, name_to_find)
            return datetime.strptime(text, format).date() if text else None

        def tag2decimal(tag: Any,
                        name_to_find: str) -> Optional[Decimal]:
            text: Optional[str] = tag2text(tag, name_to_find)
            return Decimal(text) if text else None

        logger.debug("File to read: %s\n", ofx_file)

        with open(ofx_file, 'r') as f:
            soup = BeautifulSoup(f, 'html.parser')

            for banktranlist in soup.find_all('banktranlist'):
                logger.debug("banktranlist: %s\n", banktranlist)
                bankacctfrom = banktranlist.parent.bankacctfrom
                acctid: Optional[str]
                if bankacctfrom:
                    logger.debug("bankacctfrom: %s\n", bankacctfrom)
                    acctid = tag2text(bankacctfrom, 'acctid')
                    if acctid:
                        for tr in banktranlist('stmttrn'):
                            logger.debug("stmttrn: %s\n", tr)
                            fitid: Optional[str] = tag2text(tr, 'fitid')

                            assert fitid is not None
                            self.add(ofx_file,
                                     fitid,
                                     acctid,
                                     tag2text(tr, 'checknum'),
                                     tag2date(tr, 'dtposted', '%Y%m%d'),
                                     tag2decimal(tr, 'trnamt'),
                                     tag2text(tr, 'name'),
                                     tag2text(tr, 'memo'))

    def add(self,
            ofx_file: str,
            id: str,
            account_id: str,
            check_no: Optional[str],
            dtposted: Optional[date],
            amount: Optional[Decimal],
            payee: Optional[str],
            memo: Optional[str]) -> None:
        """Set the transaction: up to three possible keys may be added"""
        assert check_no or payee

        # see cases 1 till 3 above
        min_case: int = 1
        max_case: int = 2  # 3

        if check_no and payee:
            pass
        elif check_no:
            max_case = 1
        elif payee:
            min_case = 2
            max_case = 2

        data: TransactionData = TransactionData.make(ofx_file,
                                                     id,
                                                     payee,
                                                     memo)

        if account_id not in self.unique_id_sets:
            self.unique_id_sets[account_id] = set()

        self.unique_id_sets[account_id].add(id)

        for case in range(min_case, max_case + 1):
            key: TransactionKey = TransactionKey.make(account_id,
                                                      check_no if case != 2 else None,  # nopep8
                                                      dtposted,
                                                      amount,
                                                      payee if case != 1 else None)  # nopep8

            msg: str = 'key (%r) and data (%r)' % (key, data)

            found: TransactionData = self.cache.get(key, data)

            differences = found._asdict().items() ^ data._asdict().items()
            different_attributes = set([k for k, v in differences])

            if found == data:
                self.cache[key] = data  # new data
            elif different_attributes.issubset(set(['ofx_file', 'id'])):
                # merge old and new data (new gets precedence but only if defined)  # nopep8
                result: TransactionData = TransactionData.merge(data, found)
                logger.info("Merging transaction data\nsrc: %r\ndst: %r\nres: %r",  # nopep8
                            data,
                            found,
                            result)
                self.cache[key] = result
            else:
                raise ValidationError(
                    '\nDifferent transaction data found.\nkey: %r\nnew: %r\nold: %r\ndifferences: %r\ndifferent attributes: %r' %  # nopep8
                    (key, data, found, differences, different_attributes), self)  # nopep8

            logger.debug('Adding %s', msg)

    def print(self, msg: str) -> None:
        """Print the cache.
        """
        logger.debug('%s', msg)
        for key in self.cache:
            logger.debug('key: %r; data: %r',
                         key,
                         self.cache[key])

    def lookup(self,
               stmt_line: StatementLine,
               account_id: str) -> None:
        key: TransactionKey
        data: TransactionData
        check_no: Optional[str]
        name: Optional[str]
        # see cases 1 till 3 above
        min_case: int = 1
        max_case: int = 3

        if stmt_line.payee == 'VIREMENT SEPA':
            check_no = stmt_line.check_no
            name = stmt_line.memo
        else:
            check_no = stmt_line.check_no
            name = None  # stmt_line.payee

        if check_no and name:
            pass
        elif check_no:
            max_case = 1
        elif name:
            min_case = 2
            max_case = 2
        else:
            return

        # we should start with the most specific key
        # for case in range(max_case, max_case - 1, -1):  try the most specific
        for case in range(max_case, min_case - 1, -1):
            # The PDF may differ from the OFX by a different date
            # or a switch from payee to memo or otherwise: forget them
            for dt in [stmt_line.accounting_date,
                       stmt_line.operation_date,
                       stmt_line.value_date]:
                assert type(dt) is date, "Type of {} should be date".format(dt)

                key = TransactionKey.make(account_id,
                                          check_no if case != 2 else None,  # nopep8,
                                          dt,
                                          stmt_line.amount,
                                          name if case != 1 else None)  # nopep8

                if key in self.cache:
                    data = self.cache[key]
                    logger.info('Found id (%s)\nstatement line: %r\nkey: %r\ndata: %r',  # nopep8
                                data.id, stmt_line, key, data)
                    stmt_line.date = datetime.combine(dt, datetime.min.time())
                    stmt_line.id = data.id
                    stmt_line.payee = data.name
                    stmt_line.memo = data.memo
                    return
                else:
                    logger.debug('Did not find value for key %r', key)

        if not self.printed:
            self.print('try_cache: no data found')
            self.printed = True

        return

    def get_unique_id_set(self, account_id: str) -> Set[str]:
        return self.unique_id_sets[account_id]

    def set_unique_id_set(self, account_id: str, id_set: Set[str]) -> None:
        self.unique_id_sets[account_id] = id_set
