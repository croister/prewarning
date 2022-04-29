# -*- coding: utf-8 -*-

from typing import Callable, Any, Iterable, Tuple


class ValidationError(Exception):

    def __init__(self, function: Callable, message: str, args: Iterable[Tuple[str, Any]]):
        self.function = function
        self.message = message
        self.__dict__.update(args)

    def __repr__(self):
        return 'ValidationError(function={function}, message={message}, args={args})'.format(
            function=self.function.__name__,
            message=self.message,
            args=dict(
                [(k, v) for (k, v) in self.__dict__.items() if k != 'function' and k != 'message']
            )
        )

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return repr(self)

    def __bool__(self):
        return False
