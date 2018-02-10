import logging
import logging.config
import json
import yaml

from notifier.manager import NotifierManager


class Receiver():
    def __init__(self, config):
        # Setup logging
        with open('logging.yaml') as f:
            logging.config.dictConfig(yaml.load(f))

        logging.getLogger().setLevel(logging.INFO)

        # Remove logging of each sent request to discord
        logging.getLogger('requests').setLevel(logging.WARNING)

        self.notifiermanager = NotifierManager(config)
        self.notifiermanager.start()


    def process(self, request_body):
        data = json.loads(request_body)
        if type(data) == dict:
            self.notifiermanager.enqueue(data)
        else:
            for frame in data:
                self.notifiermanager.enqueue(frame)

        return ""
