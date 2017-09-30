from .utils import *
import logging

log = logging.getLogger(__name__)


class NotificationHandler(object):
    def __init__(self):
        pass

    def notify_pokemon(self, settings, pokemon):
        raise NotImplementedError("abstract method")

    def notify_gym(self, endpoint, gym):
        raise NotImplementedError("abstract method")

    def notify_raid(self, endpoint, raid):
        raise NotImplementedError("abstract method")