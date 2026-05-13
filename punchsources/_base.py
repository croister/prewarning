# -*- coding: utf-8 -*-

from abc import abstractmethod, ABC
import logging
from typing import Dict, Callable, List

import wx

from utils.config import ConfigConsumer
from utils.config_definitions import ConfigOptionDefinition


class PunchListener(ABC):

    def __repr__(self) -> str:
        return 'PunchListener()'

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

    def punch_received(self, punch: Dict[str, str]):
        pass


_NOT_OVERRIDDEN = object()


class _PunchSourceBase(ConfigConsumer):
    """
    Base class for Punch Sources.
    """

    name = _NOT_OVERRIDDEN

    display_name = _NOT_OVERRIDDEN

    description = _NOT_OVERRIDDEN

    def __repr__(self) -> str:
        return f'_PunchSourceBase(name={self.name})'

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def __init__(self) -> None:
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        self.punch_listeners: set[PunchListener] = set()
        self._tracking_listeners: List[Callable] = []

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

    def register_tracking_listener(self, callback: Callable):
        """Register a callback to receive tracking state updates.

        The callback is invoked via wx.CallAfter on each tracking state change.
        It receives a dict mapping option definition names to their current values.
        """
        if callback not in self._tracking_listeners:
            self._tracking_listeners.append(callback)

    def unregister_tracking_listener(self, callback: Callable):
        if callback in self._tracking_listeners:
            self._tracking_listeners.remove(callback)

    def _notify_tracking_listeners(self):
        if not self._tracking_listeners:
            return
        state = self._get_tracking_state()
        for callback in self._tracking_listeners:
            wx.CallAfter(callback, state)

    def _get_tracking_state(self) -> Dict[str, str]:
        """Override in subclasses to return current tracking values by name."""
        return {}

    def get_runtime_value(self, option_definition: ConfigOptionDefinition):
        """Return the current runtime value for the given option definition, or None."""
        return None

    def set_runtime_value(self, option_definition: ConfigOptionDefinition, value: str):
        """Set a runtime tracking value. Override in subclasses."""

    def reset_tracking(self):
        """Reset tracking state to defaults. Override in subclasses."""
