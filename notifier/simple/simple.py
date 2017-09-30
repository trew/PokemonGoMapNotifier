from .. import NotificationHandler
import logging

log = logging.getLogger(__name__)


class Simple(NotificationHandler):
    def notify_pokemon(self, endpoint, pokemon):
        log.info(pokemon)

    def notify_gym(self, endpoint, gym):
        log.info(gym.get('trainer_name') + " joined " + gym.get('name'))

    def notify_raid(self, endpoint, raid, gym):
        log.info("%s raid starting %s (%s left) at %s!" % (raid.get('name'),
                                                           raid.get('start'),
                                                           raid.get('time_until_start'),
                                                           gym.get('name')))
