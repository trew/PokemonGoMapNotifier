# For running standalone using Flask and Gevent

import configargparse
import logging

from flask import Flask, request
from gevent import wsgi

from server import Receiver


app = Flask(__name__)


@app.route('/', methods=['POST'])
def webhook_receiver():
    receiver.process(request.data)


if __name__ == '__main__':
    parser = configargparse.ArgParser()
    parser.add_argument('--host', help='Host', default='localhost')
    parser.add_argument('-p', '--port', help='Port', type=int, default=8000)
    parser.add_argument('-c', '--config', help="config.json file to use", default="config/config.json")
    args = parser.parse_args()
 
    receiver = Receiver(args.config)

    # Removes logging of each received request to flask server
    logging.getLogger('pywsgi').setLevel(logging.WARNING)

    logging.getLogger().info("Webhook server started on http://{}:{}".format(args.host, args.port))

    server = wsgi.WSGIServer((args.host, args.port), app, log=logging.getLogger('pywsgi'))
    server.serve_forever()
