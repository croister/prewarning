# -*- coding: utf-8 -*-

import re

# Matches the label part in a Fully Qualified Domain Name (FQDN) or Domain Name.
DOMAIN_NAME_LABEL_PATTERN_STR = r'([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])'
DOMAIN_NAME_LABEL_PATTERN = re.compile(r'^{label}$'.format(label=DOMAIN_NAME_LABEL_PATTERN_STR))

# Matches the Global Top Level Domain (gTLD) part of a Fully Qualified Domain Name (FQDN) or Domain Name.
DOMAIN_NAME_TLD_PATTERN_STR = r'([a-zA-Z][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])'
DOMAIN_NAME_TLD_PATTERN = re.compile(r'^{tld}$'.format(tld=DOMAIN_NAME_TLD_PATTERN_STR))

# Matches a bare Hostname.
HOSTNAME_PATTERN = DOMAIN_NAME_LABEL_PATTERN

# Matches a Fully Qualified Domain Name (FQDN).
HOSTNAME_FQDN_PATTERN = re.compile(r'^(?:{label}\.)+{tld}$'.format(label=DOMAIN_NAME_LABEL_PATTERN_STR,
                                                                   tld=DOMAIN_NAME_TLD_PATTERN_STR))

# Matches a Domain Name.
DOMAIN_NAME_PATTERN = re.compile(r'^(?:{label}\.)*{tld}$'.format(label=DOMAIN_NAME_LABEL_PATTERN_STR,
                                                                 tld=DOMAIN_NAME_TLD_PATTERN_STR))
