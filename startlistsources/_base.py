# -*- coding: utf-8 -*-

from abc import abstractmethod
import logging
from typing import Dict

from utils.config_consumer import ConfigConsumer


_NOT_OVERRIDDEN = object()


class _StartListSourceBase(ConfigConsumer):
    """
    Base class for Start List Sources.
    """

    name = _NOT_OVERRIDDEN

    display_name = _NOT_OVERRIDDEN

    description = _NOT_OVERRIDDEN

    def __repr__(self) -> str:
        return "_StartListSourceBase()"

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def start(self):
        """Starts the StartListSource."""

    @abstractmethod
    def stop(self):
        """Stops the StartListSource."""

    @abstractmethod
    def is_running(self) -> bool:
        """Returns if the StartListSource is running."""

    @abstractmethod
    def lookup_from_card_number(self, card_number: str) -> Dict[str, str] | None:
        """Returns Bib-Number and Relay Leg for the provided Card Number.

        :param str card_number: The Card Number to look up.
        :return: A dict with the Bib-Number (bibNumber) and Relay Leg (relayLeg).
        :rtype: Dict[str, Str] or None
        """
        return dict()
