from .. import NotificationHandler
import logging

log = logging.getLogger(__name__)


class Simple(NotificationHandler):
    def notify_pokemon(self, endpoint, pokemon):
        log.info(pokemon)

    def notify_gym(self, endpoint, gym):
        log.info(gym.get('trainer_name') + " joined " + gym.get('name'))