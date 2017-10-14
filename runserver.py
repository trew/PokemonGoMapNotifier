from flask import Flask, request
from gevent import wsgi

from notifier.manager import NotifierManager

import logging
import logging.handlers
import logging.config
import json
import yaml
import configargparse


def log_setup():
    with open('logging.yaml') as f:
        logging.config.dictConfig(yaml.load(f))

    return logging.getLogger()


app = Flask(__name__)


@app.route('/', methods=['POST'])
def webhook_receiver():
    data = json.loads(request.data)
    if type(data) == dict:
        notifiermanager.enqueue(data)
    else:
        for frame in data:
            notifiermanager.enqueue(frame)

    return ""


if __name__ == '__main__':
    # Setup logging
    log = log_setup()
    log.setLevel(logging.INFO)

    # Removes logging of each received request to flask server
    logging.getLogger('pywsgi').setLevel(logging.WARNING)

    # Remove logging of each sent request to discord
    logging.getLogger('requests').setLevel(logging.WARNING)

    parser = configargparse.ArgParser()
    parser.add_argument('--host', help='Host', default='localhost')
    parser.add_argument('-p', '--port', help='Port', type=int, default=8000)
    parser.add_argument('-c', '--config', help="config.json file to use", default="config/config.json")
    args = parser.parse_args()

    notifiermanager = NotifierManager(args.config)
    notifiermanager.start()

    log.info("Webhook server started on http://{}:{}".format(args.host, args.port))
    server = wsgi.WSGIServer((args.host, args.port), app, log=logging.getLogger('pywsgi'))
    server.serve_forever()
