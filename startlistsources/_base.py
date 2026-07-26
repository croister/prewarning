import logging
from abc import abstractmethod
from collections.abc import Callable

from utils.config_consumer import ConfigConsumer
from utils.health import HealthStatus

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
        self._data_listeners: list[Callable[[], None]] = []
        self._health_listeners: list[Callable[[], None]] = []
        self._health_status: HealthStatus = HealthStatus.OK
        self._health_message: str | None = None

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
    def lookup_from_card_number(self, card_number: str) -> dict[str, str] | None:
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
        return {}

    def get_bib_range(self) -> tuple[int, int] | None:
        """Returns the range of bib numbers in the start list.

        :return: A tuple (min_bib, max_bib), or None if no data is available.
        :rtype: tuple[int, int] or None
        """
        return None

    def get_team_count(self) -> int | None:
        """Returns the number of teams in the start list, or None if unavailable."""
        return None

    def get_runner_count(self) -> int | None:
        """Returns the number of runners (SI cards) in the start list, or None if unavailable."""
        return None

    def register_data_listener(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked when start list data changes."""
        if callback not in self._data_listeners:
            self._data_listeners.append(callback)

    def unregister_data_listener(self, callback: Callable[[], None]) -> None:
        """Unregister a previously registered data listener."""
        if callback in self._data_listeners:
            self._data_listeners.remove(callback)

    def _notify_data_changed(self) -> None:
        """Notify all registered data listeners that start list data has changed."""
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
