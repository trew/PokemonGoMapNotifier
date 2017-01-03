from .. import NotificationHandler
import logging

log = logging.getLogger(__name__)


class Simple(NotificationHandler):
    def notify_pokemon(self, settings, pokemon):
        log.info(pokemon)
