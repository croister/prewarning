from pathlib import Path

# The directory where this file is located
APPLICATION_DIR = Path(__file__).resolve().parent.parent.absolute()

# The name of the directory where the configuration files are located
CONFIGURATION_DIR_NAME = "config"

# The directory where the configuration files are located
CONFIGURATION_DIR = APPLICATION_DIR / CONFIGURATION_DIR_NAME

# The name of the directory where the configuration files are located
DATA_DIR_NAME = "data"

# The directory where the configuration files are located
DATA_DIR = APPLICATION_DIR / DATA_DIR_NAME

# -- Punch dict keys -----------------------------------------------------------
# Keys used in the punch dict passed between punch sources, start list sources,
# and the main application.

PUNCH_KEY_ID = "id"
PUNCH_KEY_CONTROL_CODE = "controlCode"
PUNCH_KEY_CARD_NUMBER = "cardNumber"
PUNCH_KEY_PASSED_TIME = "passedTime"
PUNCH_KEY_BIB_NUMBER = "bibNumber"
PUNCH_KEY_RELAY_LEG = "relayLeg"
PUNCH_KEY_COUNTRY = "country"
PUNCH_KEY_IS_LAST_LEG = "isLastLeg"

# Valid values for fetch interval config options (1-120 seconds)
FETCH_INTERVAL_VALID_VALUES = list(range(1, 121))

# The file extension used for audio files
AUDIO_EXTENSION = ".mp3"

# The default ding sound file name
DING_FILENAME = f"ding{AUDIO_EXTENSION}"

# The file name for the Testing onem two, three sound
TESTING_FILENAME = f"Testing{AUDIO_EXTENSION}"
