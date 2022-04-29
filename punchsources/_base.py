# -*- coding: utf-8 -*-

from abc import abstractmethod, ABC
import logging
from typing import Dict

from utils.config import ConfigConsumer


class PunchListener(ABC):

    def __repr__(self) -> str:
        return f'PunchListener()'

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

    def punch_received(self, punch: Dict[str, str]):
        pass


class _PunchSourceBase(ConfigConsumer):
    """
    Base class for Punch Sources.
    """

    name = NotImplemented

    display_name = NotImplemented

    description = NotImplemented

    def __repr__(self) -> str:
        return f'_PunchSourceBase(name={self.name})'

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        self.punch_listeners = set()

    @abstractmethod
    def start(self):
        """Starts the PunchSource.
        """

    @abstractmethod
    def stop(self):
        """Stops the PunchSource.
        """

    @abstractmethod
    def is_running(self) -> bool:
        """Returns if the PunchSource is running.
        """

    def register_punch_listener(self, listener: PunchListener):
        """Registers a Punch Listener that will be notified when a Punch is received.

        :param PunchListener listener: The listener to register
        """
        self.punch_listeners.add(listener)

    def _notify_punch_listeners(self, punch: Dict[str, str]):
        """Notifies all Punch Listeners that a punch has been received.

        :param Dict[str, str] punch: The punch to notify about
        """
        for listener in self.punch_listeners:
            listener.punch_received(punch)
