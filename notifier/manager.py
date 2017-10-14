from threading import Thread
from .config import Config
from .handler import Handler
from .notifier import Notifier
from .utils import *
import logging
import Queue

log = logging.getLogger(__name__)


class NotifierManager(Thread):
    def __init__(self, config_file):
        super(NotifierManager, self).__init__()

        self.daemon = True
        self.name = "Notifier"

        self.config = Config(config_file)
        self.notifier = Notifier(self.config)
        self.handler = Handler(self.config, self.notifier)

        self.queue = Queue.Queue()

    def run(self):
        log.info('Notifier thread started.')

        while True:
            for i in range(0, 5000):
                data = self.queue.get(block=True)

                message_type = data.get('type')

                if message_type == 'pokemon':
                    self.handler.handle_pokemon(data['message'])
                elif message_type == 'gym_details':
                    self.handler.handle_gym_details(data['message'])
                elif message_type == 'raid':
                    self.handler.handle_raid(data['message'])
                else:
                    log.debug('Unsupported message type: %s', message_type)
            self.handler.clean()

    def enqueue(self, data):
        self.queue.put(data)

