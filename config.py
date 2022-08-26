# Local PACS configuration

DEBUG = True
USE_DEBUG_LOGGER = False
IP = "0.0.0.0"
PORT = 7001

STORAGE_TYPE = 'files'
STORAGE_DESTINATION = 'Stored'

TRUSTED = dict(
    STORE_SCP=('0.0.0.0', PORT + 1)
)
