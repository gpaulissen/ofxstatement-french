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


class TransactionKey(NamedTuple):
    account_id: str
    dtposted: Optional[date]
    trnamt: Optional[Decimal]

    @staticmethod
    def make(account_id: str,
             dtposted: Optional[date],
             amount: Optional[Decimal]) -> 'TransactionKey':
        assert isinstance(account_id, str), \
            "account_id (%s) must be an instance of str" % (type(account_id))
        assert dtposted is None or isinstance(dtposted, date), \
            "dtposted (%s) must be an instance of date" % (type(dtposted))
        assert amount is None or isinstance(amount, Decimal), \
            "amount (%s) must be an instance of Decimal" % (type(amount))

        return TransactionKey(account_id,
                              dtposted,
                              amount)


class TransactionData(NamedTuple):
    checknum: Optional[str]
    name: Optional[str]  # for VIREMENT SEPA
    memo: Optional[str]
    id: str
    ofx_file: str

    @staticmethod
    def make(check_no: Optional[str],
             payee: Optional[str],
             memo: Optional[str],
             id: str,
             ofx_file: str) -> 'TransactionData':
        assert check_no is None or isinstance(check_no, str), \
            "check_no (%s) must be an instance of str" % (type(check_no))
        assert payee is None or isinstance(payee, str), \
            "payee (%s) must be an instance of str or None" % (type(payee))
        assert memo is None or isinstance(memo, str), \
            "memo (%s) must be an instance of str or None" % (type(memo))
        assert isinstance(id, str), \
            "id (%s) must be an instance of str" % (type(id))
        assert isinstance(ofx_file, str), \
            "ofx_file (%s) must be an instance of str" % (type(ofx_file))

        # If payee or memo is not empty there may be a whitespace difference
        # so remove multiple whitespace characters by a single one
        payee = ' '.join(payee.split()) if payee else None
        memo = ' '.join(memo.split()) if memo else None

        return TransactionData(None if check_no == '' else check_no,
                               None if payee == '' else payee,
                               None if memo == '' else memo,
                               id,
                               ofx_file)

    def match(self, td: 'TransactionData') -> int:
        def cmp(i1: Optional[Any], i2: Optional[Any]) -> int:
            if not 11 and not i2:
                return 0
            elif not 11:
                return -1
            elif not i2:
                return +1
            elif str(i1) < str(i2):
                return -2
            elif str(i1) > str(i2):
                return +2
            else:
                return 0

        results = [cmp(' ' not in self.id, True),
                   cmp(self.memo, td.memo),
                   cmp(self.name, td.name),
                   cmp(self.checknum, td.checknum)]
        result: int = 0

        for idx in range(len(results)):
            if results[idx] in (0, 1):
                # self.<item> = td.<item> or not td.item
                # This means that self.<item> matches td.<item>
                result = result + 2 ** idx
            elif idx == 3:
                # this (checknum) must match
                result = 0
                break

        logger.debug("match(\nself=%s,\ntd  =%s\n) = %d", self, td, result)
        return result


TRANSACTION_DATA_NR_ITEMS = 4
THRESHOLD = 2 ** (TRANSACTION_DATA_NR_ITEMS - 1 - 1)


class Transaction(NamedTuple):
    """
    A typical OFX transaction record is:

      <STMTTRN>
        <TRNTYPE>CREDIT
        <DTPOSTED>20191126
        <TRNAMT>+248.21
        <FITID>201901100044BD27
        <CHECKNUM>F6KJAIV
        <NAME>EVI DRFIP NOUVELLE AQUIT
        <MEMO>REMUNERATION DU 11/2019. MINISTE RE : 206 GESTION : 991-033
      </STMTTRN>

    A matching PDF transaction record may be:

      accounting_date: 26/11/2019
      payee: VIREMENT SEPA
      operation_date: 26/11/2019
      value_date: 26/11/2019
      amount: 248,21
      memo: EVI DRFIP NOUVELLE AQUIT
      check_no: -

    The unique key of an OFX transaction is FITID (used by beancount) and
    this key will be looked up for the PDF transactions since
    they do not contain this information.

    In order to look up the FITID these properties MUST be the same:
    1. account id;
    2. date posted (DTPOSTED);
    3. transaction amount (TRNAMT).

    This will be the TransactionKey.

    For other properties it is more of a fuzzy search
    with the most important first:
    4. check number (CHECKNUM);
    5. counter party (NAME);
    6. memo (MEMO);
    7. id (FITID) where a (temporary) id containing spaces ranks the lowest;

    This will be the TransactionData.

    So for each date posted and transaction amount a set of transaction data
    based on OFX transactions will be stored.
    The program will abort on duplicates.

    Looking up given a PDF transaction:
    - for the amount and each of the three dates determine the data bucket
    - determine the highest match with bucket transaction data
    - if the highest match is below the threshold it will be discarded, i.e.
      at least check number or counter party must match

    """
    key: TransactionKey
    data: TransactionData


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

    def adjust(self,
               statement_cache: 'StatementCache',
               account_id: str) -> bool:
        check_no: Optional[str]
        payee: Optional[str]
        memo: Optional[str]
        dates: Set[date] = set((self.accounting_date,
                                self.operation_date,
                                self.value_date))
        max_match: int = -1
        this_match: int
        matches: Set[Transaction] = set()

        if self.payee == 'VIREMENT SEPA' and not self.check_no:
            check_no = None
            payee = self.memo
            memo = None
        else:
            check_no = self.check_no
            payee = self.payee
            memo = self.memo

        target: TransactionData = TransactionData.make(check_no,
                                                       payee,
                                                       memo,
                                                       '',
                                                       '')

        for idx in range(3):  # max three dates to check for
            dt: date
            if idx == 0:
                dt = self.accounting_date
            elif idx == 1:
                dt = self.operation_date
            else:
                dt = self.value_date

            if dt not in dates:
                continue

            dates.remove(dt)

            key: TransactionKey = TransactionKey.make(account_id,
                                                      dt,
                                                      self.amount)

            if key in statement_cache.cache:
                for data in statement_cache.cache[key]:
                    this_match = data.match(target)
                    if this_match < THRESHOLD or this_match < max_match:
                        continue
                    if this_match > max_match:
                        max_match = this_match
                        # remove previous matches and replace by this one
                        matches.clear()
                    matches.add(Transaction(key, data))

        m: Transaction

        # invariant: all entries in matches must have the same match
        for m in matches:
            logger.debug('match: %s', m.data)
            assert m.data.match(target) == max_match

        max_dt: Optional[date] = None
        found: Optional[TransactionData] = None

        # Take one match (found) and check against the other matches:
        # the difference must be below the threshold otherwise
        # either checknum or name differs.
        if len(matches) > 0:
            m = matches.pop()
            max_dt, found = m.key.dtposted, m.data
            logger.debug('found: %s', found)
            assert found.match(target) == max_match

        if max_dt is not None and found is not None:
            for m in matches:
                this_match = m.data.match(found)
                if this_match >= THRESHOLD:
                    # the difference between two possible matches is too much
                    found = None
                    break

        # still ok?
        if max_dt is None or found is None:
            logger.debug('Could not find a match for %r', self)
        else:
            logger.debug('Found a match for %r:\n%r', self, found)
            self.date = datetime.combine(max_dt, datetime.min.time())
            self.id = found.id
            if self.payee == 'VIREMENT SEPA' and not self.check_no:
                # overwrite these attributes
                self.check_no = found.checknum
                self.payee = found.name
                self.memo = found.memo
            else:
                # set these attributes if empty
                self.check_no = found.checknum if not self.check_no else self.check_no  # nopep8
                self.payee = found.name if not self.payee else self.payee
                self.memo = found.memo if not self.memo else self.memo

        if not statement_cache.printed:
            statement_cache.print('try_cache: no data found')
            statement_cache.printed = True

        return found is not None


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


class StatementCache(object):
    unique_id_sets: Dict[str, Set[str]]
    ofx_files: Optional[str]
    cwd: str
    cache: Dict[TransactionKey, Set[TransactionData]]
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
        """Add the transaction"""
        key: TransactionKey = TransactionKey.make(account_id,
                                                  dtposted,
                                                  amount)
        data: TransactionData = TransactionData.make(check_no,
                                                     payee,
                                                     memo,
                                                     id,
                                                     ofx_file)
        msg: str = 'key (%r) and data (%r)' % (key, data)

        if account_id not in self.unique_id_sets:
            self.unique_id_sets[account_id] = set()
        self.unique_id_sets[account_id].add(id)

        if key not in self.cache:
            self.cache[key] = set()
        assert data not in self.cache[key], \
            'data (%r) already part of this bucket (%r)' % (data, key)
        self.cache[key].add(data)

        logger.debug('Adding %s', msg)

    def print(self, msg: str) -> None:
        """Print the cache.
        """
        logger.debug('%s', msg)
        for key in self.cache:
            logger.debug('key: %r', key)
            for data in self.cache[key]:
                logger.debug('data: %r', data)

    def get_unique_id_set(self, account_id: str) -> Set[str]:
        return self.unique_id_sets[account_id]

    def set_unique_id_set(self, account_id: str, id_set: Set[str]) -> None:
        self.unique_id_sets[account_id] = id_set
