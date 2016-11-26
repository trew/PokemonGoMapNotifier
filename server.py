#!/usr/bin/env python

import configargparse
import httplib2
import urllib
import os
import simplejson as json
from queue import Queue
from threading import Thread
from cachetools import LRUCache
import gpxpy.geo
import BaseHTTPServer
import SocketServer
import pogoidmapper


class NotifierServer:
    def __init__(self, host, port, latitude, longitude, whitelist_file, notifier_queue):
        self.host = host
        self.port = port
        self.latitude = latitude
        self.longitude = longitude
        self.thresholds, self.whitelist = self.get_thresholds_and_whitelist(whitelist_file)
        self.notifier_queue = notifier_queue
        self.cache = LRUCache(maxsize=20)

    @staticmethod
    def get_thresholds_and_whitelist(filename):
        id_to_threshold = {}
        whitelist = []
        threshold = -1

        with open(filename, 'r') as f:
            for line in f:
                if line.startswith("#"):
                    continue
                if line.startswith("Threshold:"):
                    threshold = int(line.split(":")[1].strip())
                else:
                    name = line.strip()
                    if name:
                        pokemon_id = pogoidmapper.get_pokemon_id(line.strip())
                        id_to_threshold[pokemon_id] = threshold
                        whitelist.append(pokemon_id)

        return id_to_threshold, whitelist

    def process(self, pokemon_id, distance, latitude, longitude, extras, encounter):
        """
        Processes an encountered pokemon and determines whether to send a notification or not
        """

        threshold = self.thresholds[pokemon_id]
        if distance and 0 < threshold < distance:
            # pokemon is out of range
            return

        self.cache[encounter] = 1  # cache it

        maps = "http://www.google.com/maps/place/{0},{1}".format(latitude, longitude)
        navigation = "http://maps.google.com/maps?saddr={0},{1}&daddr={2},{3}".format(self.latitude,
                                                                                      self.longitude,
                                                                                      latitude,
                                                                                      longitude)
        ivs = [extras[0], extras[1], extras[2]] if extras else None
        moves = [pogoidmapper.get_move_name(extras[3]), pogoidmapper.get_move_name(extras[4])] if extras else None

        pokemon_name = pogoidmapper.get_pokemon_name(pokemon_id)
        gamepress = "https://pokemongo.gamepress.gg/pokemon/{0}".format(pokemon_id)
        self.notifier_queue.put((pokemon_name, distance, ivs, moves, gamepress, maps, navigation))

    def run(self):
        handler = ServerHandler
        httpd = SocketServer.TCPServer((self.host, self.port), handler)
        httpd.notifier_server = self

        print "Serving at: http://{0}:{1}".format(self.host, self.port)
        httpd.serve_forever()


class ServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """
    Handles POST requests from PokemonGO Map Webhooks
    """

    def do_GET(self):
        """
        Not allowed
        """

        self.send_response(403)
        self.end_headers()

    def do_POST(self):
        """
        Processes encountered pokemons, and sends them over to the notifier server if it passed whitelist check
        """

        if self.headers['content-type'] == 'application/json':
            data_string = self.rfile.read(int(self.headers['content-length']))
            data = json.loads(data_string)
            type = data['type']

            # only check pokemon type
            if type == 'pokemon':
                message = data['message']
                pokemon_id = message['pokemon_id']
                encounter = message['encounter_id']
                move_1 = message['move_1']
                extras = None

                # have this exact encounter been processed recently?
                if encounter not in self.server.notifier_server.cache.keys():

                    if pokemon_id in self.server.notifier_server.whitelist:
                        if move_1:
                            move_2 = message['move_2']
                            iv_att = message['individual_attack']
                            iv_def = message['individual_defense']
                            iv_sta = message['individual_stamina']
                            extras = (iv_att, iv_def, iv_sta, move_1, move_2)

                        latitude = message['latitude']
                        longitude = message['longitude']

                        has_distance = self.server.notifier_server.latitude and self.server.notifier_server.longitude
                        distance = get_distance(float(self.server.notifier_server.latitude),
                                                float(self.server.notifier_server.longitude),
                                                float(latitude),
                                                float(longitude)) if has_distance else None

                        self.server.notifier_server.process(pokemon_id, distance, latitude, longitude, extras,
                                                            encounter)

        self.send_response(200)
        self.end_headers()


def get_simple_formatting(pokemon_name, distance, ivs, moves, gamepress, maps, navigation):
    """
    Processes an encountered pokemon and determines whether to send a notification or not
    """

    extra_str = ""
    if ivs and moves:
        iv_percent = int((float(ivs[0]) + float(ivs[1]) + float(ivs[2])) / 45 * 100)
        extra_str = "IV: {0}/{1}/{2} {3}%\nMoves:\n* {4}\n* {5}\n{6}\n\n".format(ivs[0],
                                                                                 ivs[1],
                                                                                 ivs[2],
                                                                                 iv_percent,
                                                                                 moves[0],
                                                                                 moves[1],
                                                                                 gamepress)

    distance_str = "Distance is {0}m.\n\n".format(distance) if distance else ""

    maps_and_navigation = "Google Maps: {0}\n\nNavigation: {1}".format(maps, navigation)

    title = "{0} found!".format(pokemon_name)
    body = "{0}{1}{2}".format(distance_str, extra_str, maps_and_navigation)

    return title, body


def notify_simple(pokemon_name, distance, ivs, moves, gamepress, maps, navigation, extras):
    title, body = get_simple_formatting(pokemon_name, distance, ivs, moves, gamepress, maps, navigation)
    print "{0}\n{1}".format(title, body)


def notify_pushbullet(pokemon_name, distance, ivs, moves, gamepress, maps, navigation, extras):
    title, body = get_simple_formatting(pokemon_name, distance, ivs, moves, gamepress, maps, navigation)

    url = 'https://api.pushbullet.com/v2/pushes'
    headers = {'Content-type': 'application/x-www-form-urlencoded'}
    API_KEY = extras['PUSHBULLET_API_KEY']

    http = httplib2.Http()
    http.add_credentials(API_KEY, '')
    body = {
        'type': 'note',
        'title': title,
        'body': body,
    }
    try:
        resp, cont = http.request(url, 'POST', headers=headers,
        body=urllib.urlencode(body))
    except Exception as e:
        print "Exception {}".format(e)
    else:
        if int(resp['status']) != 200:
            try:
                error_json = json.loads(cont)
            except json.JSONDecodeError:
                print "Couldn't decode json."
            else:
                desc = error_json['error']['message']
                print "Error: {} {}".format(resp['status'], desc)
        else:
            print 'Pushbullet message sent: ' + title
            pass


def notifier(methods_and_extras, q):
    while True:
        try:
            while True:
                pokemon_name, distance, ivs, moves, gamepress, maps, navigation = q.get()
                for method_and_extra in methods_and_extras:
                    try:
                        method = method_and_extra[0]
                        extras = method_and_extra[1]
                        method(pokemon_name, distance, ivs, moves, gamepress, maps, navigation, extras)
                    except Exception as e1:
                        print "Exception in notifier(%s): %s", method.__name__, e1
                q.task_done()
        except Exception as e:
            print "Exception in notifier: %s", e


def get_distance(lat1, lon1, lat2, lon2):
    return int(gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2))


def main():
    parser = configargparse.ArgParser()
    parser.add_argument('--host', help='Host', default='localhost')
    parser.add_argument('-p', '--port', help='Port', type=int, default=8000)
    parser.add_argument('-w', '--whitelist', help='Whitelist file', default='whitelist.txt')
    parser.add_argument('-lat', '--latitude', help='Latitude which will be used to determine distance to pokemons', type=float)
    parser.add_argument('-lon', '--longitude', help='Longitude which will be used to determine distance to pokemons', type=float)
    parser.add_argument('-pb', '--pushbullet', help='Set if pushbullet should be notified')
    args = parser.parse_args()

    if 'PUSHBULLET_API_KEY' in os.environ:
        PUSHBULLET_API_KEY = os.environ['PUSHBULLET_API_KEY']

    # Define methods that will notify different services
    notify_methods = []

    if args.pushbullet:
        print "Notifying to pushbullet"
        notify_methods.append((notify_pushbullet, {'PUSHBULLET_API_KEY': PUSHBULLET_API_KEY}))

    if not notify_methods:
        print "Printing simple notifications"
        notify_methods.append((notify_simple, {}))

    # set up the notification thread
    notifier_queue = Queue()
    t = Thread(target=notifier,
               name='Notifier',
               args=(notify_methods, notifier_queue))
    t.daemon = True
    t.start()

    # Start the server
    server = NotifierServer(args.host, args.port, args.latitude, args.longitude, args.whitelist, notifier_queue)
    server.run()


if __name__ == '__main__':
    main()

