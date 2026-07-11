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
        """Returns team information for the provided Card Number.

        The returned dict must contain these keys:
          - bibNumber (str): the team bib number
          - relayLeg (int): the relay leg number
          - isLastLeg (bool): whether this is the last leg of the relay
          - country (str | None): IOC country code for voice selection

        See ``utils.constants`` for the key name constants
        (PUNCH_KEY_BIB_NUMBER, PUNCH_KEY_RELAY_LEG, etc.).

        :param str card_number: The Card Number to look up.
        :return: A dict with the team information, or None if not found.
        :rtype: Dict[str, str] or None
        """
        return dict()

    def get_bib_range(self) -> tuple[int, int] | None:
        """Returns the range of bib numbers in the start list.

        :return: A tuple (min_bib, max_bib), or None if no data is available.
        :rtype: tuple[int, int] or None
        """
        return None
