# -*- coding: utf-8 -*-
from pathlib import Path

# The directory where this file is located
APPLICATION_DIR = Path(__file__).resolve().parent.parent.absolute()

# The name of the directory where the configuration files are located
CONFIGURATION_DIR_NAME = 'config'

# The directory where the configuration files are located
CONFIGURATION_DIR = APPLICATION_DIR / CONFIGURATION_DIR_NAME

# The name of the directory where the configuration files are located
DATA_DIR_NAME = 'data'

# The directory where the configuration files are located
DATA_DIR = APPLICATION_DIR / DATA_DIR_NAME
