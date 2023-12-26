# -*- coding: utf-8 -*-

from typing import Optional

from datetime import date

from ofxstatement.statement import Statement as BaseStatement
from ofxstatement.exceptions import ValidationError


class Statement(BaseStatement):
    def __init__(self,
                 parent: Optional[BaseStatement] = None) -> None:
        super().__init__()
        if parent:
            self.__dict__ = parent.__dict__.copy()

    def assert_valid(self) -> None:
        try:
            super().assert_valid()
            assert self.end_date, "The statement end date should be set"
            dates = [getattr(sl, 'accounting_date') for sl in self.lines]
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
