import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Use StreamHandler instead of FileHandler
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)