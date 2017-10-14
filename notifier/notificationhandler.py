from .utils import *
import logging

log = logging.getLogger(__name__)


class NotificationHandler(object):
    def __init__(self):
        pass

    def notify_pokemon(self, endpoint, pokemon):
        raise NotImplementedError("abstract method")

    def notify_gym(self, endpoint, gym):
        raise NotImplementedError("abstract method")

    def notify_raid(self, endpoint, raid):
        raise NotImplementedError("abstract method")

    def notify_egg(self, endpoint, egg):
        raise NotImplementedError("abstract method")
