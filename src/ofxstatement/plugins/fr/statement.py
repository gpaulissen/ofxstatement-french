# -*- coding: utf-8 -*-

from typing import Optional

from datetime import date, datetime
from decimal import Decimal as D

from ofxstatement.statement import Statement as BaseStatement
from ofxstatement.statement import StatementLine as BaseStatementLine
from ofxstatement.exceptions import ValidationError


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
                 amount: Optional[D] = None,
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
