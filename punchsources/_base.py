import logging
from abc import ABC, abstractmethod
from collections.abc import Callable

import wx

from utils.config import ConfigConsumer
from utils.config_definitions import ConfigOptionDefinition
from utils.health import HealthStatus


class PunchListener(ABC):
    def __repr__(self) -> str:
        return "PunchListener()"

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

    def punch_received(self, punch: dict[str, str]):
        """Called when a punch is received.

        The punch dict follows the contract documented in
        ``_PunchSourceBase._notify_punch_listeners``.
        """


_NOT_OVERRIDDEN = object()


class _PunchSourceBase(ConfigConsumer):
    """
    Base class for Punch Sources.
    """

    name = _NOT_OVERRIDDEN

    display_name = _NOT_OVERRIDDEN

    description = _NOT_OVERRIDDEN

    def __repr__(self) -> str:
        return f"_PunchSourceBase(name={self.name})"

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def __init__(self) -> None:
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        self.punch_listeners: set[PunchListener] = set()
        self._tracking_listeners: list[Callable] = []
        self._data_listeners: list[Callable[[], None]] = []
        self._health_listeners: list[Callable[[], None]] = []
        self._health_status: HealthStatus = HealthStatus.OK
        self._health_message: str | None = None

    @abstractmethod
    def start(self):
        """Starts the PunchSource."""

    @abstractmethod
    def stop(self):
        """Stops the PunchSource."""

    @abstractmethod
    def is_running(self) -> bool:
        """Returns if the PunchSource is running."""

    def register_punch_listener(self, listener: PunchListener):
        """Registers a Punch Listener that will be notified when a Punch is received.

        :param PunchListener listener: The listener to register
        """
        self.punch_listeners.add(listener)

    def _notify_punch_listeners(self, punch: dict[str, str]):
        """Notifies all Punch Listeners that a punch has been received.

        The punch dict must contain these keys:
          - id (str): unique punch identifier
          - controlCode (str): the control code
          - cardNumber (str): the SI card number
          - passedTime (datetime | None): time the runner passed the control

        The ``passedTime`` value **must** be a ``datetime`` object
        (or ``None`` as a last resort). New punch sources must convert
        their native timestamp to ``datetime`` before inserting into
        the dict.

        See ``utils.constants`` for the key name constants
        (PUNCH_KEY_ID, PUNCH_KEY_CONTROL_CODE, etc.).

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

    def _get_tracking_state(self) -> dict[str, str]:
        """Override in subclasses to return current tracking values by name."""
        return {}

    def get_runtime_value(self, option_definition: ConfigOptionDefinition):
        """Return the current runtime value for the given option definition, or None."""
        return

    def set_runtime_value(self, option_definition: ConfigOptionDefinition, value: str):
        """Set a runtime tracking value. Override in subclasses."""

    def reset_tracking(self):
        """Reset tracking state to defaults. Override in subclasses."""

    def register_data_listener(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked when source data changes."""
        if callback not in self._data_listeners:
            self._data_listeners.append(callback)

    def unregister_data_listener(self, callback: Callable[[], None]) -> None:
        """Unregister a previously registered data listener."""
        if callback in self._data_listeners:
            self._data_listeners.remove(callback)

    def _notify_data_changed(self) -> None:
        """Notify all registered data listeners that source data has changed."""
        for callback in self._data_listeners:
            try:
                callback()
            except Exception:
                self.logger.exception("Error in data listener callback")

    def register_health_listener(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked when source health status changes."""
        if callback not in self._health_listeners:
            self._health_listeners.append(callback)

    def unregister_health_listener(self, callback: Callable[[], None]) -> None:
        """Unregister a previously registered health listener."""
        if callback in self._health_listeners:
            self._health_listeners.remove(callback)

    def _notify_health_changed(self) -> None:
        """Notify all registered health listeners that health status has changed."""
        for callback in self._health_listeners:
            try:
                callback()
            except Exception:
                self.logger.exception("Error in health listener callback")

    @property
    def health_status(self) -> tuple[HealthStatus, str | None]:
        """The current health status of this source as (status, message)."""
        return self._health_status, self._health_message

    def _set_health_status(
        self, status: HealthStatus, message: str | None = None
    ) -> None:
        """Set the health status and notify health listeners if it changed."""
        if self._health_status != status or self._health_message != message:
            self._health_status = status
            self._health_message = message
            self._notify_health_changed()
