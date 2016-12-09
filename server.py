#!/usr/bin/env python

import configargparse
import requests
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
    def __init__(self, host, port, latitude, longitude, whitelist, notifier_queue):
        self.host = host
        self.port = port
        self.latitude = latitude
        self.longitude = longitude
        self.whitelist = whitelist
        self.notifier_queue = notifier_queue
        self.cache = LRUCache(maxsize=20)

    def process(self, pokemon_id, distance, latitude, longitude, extras, encounter):
        """
        Processes an encountered pokemon and determines whether to send a notification or not
        """
        self.cache[encounter] = 1  # cache it

        ivs = [extras[0], extras[1], extras[2]] if extras else None
        maps = "http://www.google.com/maps/place/{0},{1}".format(latitude, longitude)
        navigation = "http://maps.google.com/maps?saddr={0},{1}&daddr={2},{3}".format(self.latitude,
                                                                                      self.longitude,
                                                                                      latitude,
                                                                                      longitude)
        moves = [pogoidmapper.get_move_name(extras[3]), pogoidmapper.get_move_name(extras[4])] if extras else None

        pokemon_name = pogoidmapper.get_pokemon_name(pokemon_id)
        gamepress = "https://pokemongo.gamepress.gg/pokemon/{0}".format(pokemon_id)
        self.notifier_queue.put((str(pokemon_id), pokemon_name, distance, ivs, moves, gamepress, maps, navigation))

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
        extra_str = "IV: {0}/{1}/{2} {3}%\nMoves:\n* {4}\n* {5}\n{6}".format(ivs[0],
                                                                             ivs[1],
                                                                             ivs[2],
                                                                             iv_percent,
                                                                             moves[0],
                                                                             moves[1],
                                                                             gamepress)

    distance_str = "Distance is {0}m.".format(distance) if distance else ""

    maps = "Google Maps: {0}".format(maps) if maps else ""
    navigation = "Navigation: {0}".format(navigation) if navigation else ""

    title = "{0} found!".format(pokemon_name)
    body = ""
    for part in (distance_str, extra_str, maps, navigation):
        if part:
            if body:
                body += "\n\n"
            body += part

    return title, body


def send(session, url, body):
    try:
        response = session.post(url, data=body)
    except Exception as e:
        print "Exception {}".format(e)
        return False
    else:
        if response.status_code != 200 and response.status_code != 204:
            print "Error: {} {}".format(response.status_code, response.reason)
            return False
        else:
            return True


def notify_simple(pokemon_id, pokemon_name, distance, ivs, moves, gamepress, maps, navigation, extras):
    title, body = get_simple_formatting(pokemon_name, distance, ivs, moves, gamepress, maps, navigation)
    print "{0}\n{1}".format(title, body)


def notify_pushbullet(pokemon_id, pokemon_name, distance, ivs, moves, gamepress, maps, navigation, extras):
    if pokemon_id not in whitelists['pushbullet']:
        return

    threshold = thresholds['pushbullet'][pokemon_id]

    if distance and 0 < threshold < distance:
        # pokemon is out of range
        # check for perfect IV
        if not ivs or sum(ivs) < 45: # return unless perfect
            return

    title, body = get_simple_formatting(pokemon_name, distance, ivs, moves, gamepress, maps, navigation)

    url = 'https://api.pushbullet.com/v2/pushes'
    headers = {'Content-type': 'application/x-www-form-urlencoded'}
    API_KEY = extras['PUSHBULLET_API_KEY']
    session = requests.Session()
    session.auth = (API_KEY, '')
    session.headers.update(headers)
    body = {
        'type': 'note',
        'title': title,
        'body': body,
    }

    body = urllib.urlencode(body)
    if send(session, url, body):
        print 'Pushbullet message sent: ' + title


def notify_discord(pokemon_id, pokemon_name, distance, ivs, moves, gamepress, maps, navigation, extras):
    if pokemon_id not in whitelists['discord']:
        return

    threshold = thresholds['discord'][pokemon_id]
    if 0 < threshold < 1000:
        return

    body = "{0} found! {1}".format(pokemon_name, maps)
    if ivs and moves:
        iv_percent = int((float(ivs[0]) + float(ivs[1]) + float(ivs[2])) / 45 * 100)
        extra_str = "IV: {0}/{1}/{2} {3}% Moves: {4} - {5}. {6}".format(ivs[0],
                                                                        ivs[1],
                                                                        ivs[2],
                                                                        iv_percent,
                                                                        moves[0],
                                                                        moves[1],
                                                                        gamepress)
    body += "\n{0}".format(extra_str) if extra_str else ""

    channel = extras['DISCORD_CHANNEL_ID']
    token = extras['DISCORD_TOKEN']
    url = 'https://discordapp.com/api/webhooks/{0}/{1}'.format(channel, token)
    headers = {'Content-type': 'application/json'}

    session = requests.Session()
    session.headers.update(headers)
    body = {
        'content': body
    }

    body = json.dumps(body)
    if send(session, url, body):
        body = body[13:body.find("found!")]
        print 'Discord notified: ' + body


def notifier(methods_and_extras, q):
    while True:
        try:
            while True:
                pokemon_id, pokemon_name, distance, ivs, moves, gamepress, maps, navigation = q.get()
                for method_and_extra in methods_and_extras:
                    try:
                        method = method_and_extra[0]
                        extras = method_and_extra[1]
                        method(int(pokemon_id), pokemon_name, distance, ivs, moves, gamepress, maps, navigation, extras)
                    except Exception as e1:
                        print "Exception in notifier(%s): %s", method.__name__, e1
                q.task_done()
        except Exception as e:
            print "Exception in notifier: %s", e


def get_distance(lat1, lon1, lat2, lon2):
    return int(gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2))


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
                    if pokemon_id not in id_to_threshold:
                        id_to_threshold[pokemon_id] = threshold
                        whitelist.append(pokemon_id)

    return id_to_threshold, whitelist


thresholds = {}
whitelists = {}

def main():
    parser = configargparse.ArgParser()
    parser.add_argument('--host', help='Host', default='localhost')
    parser.add_argument('-p', '--port', help='Port', type=int, default=8000)
    parser.add_argument('-pbwl', '--pushbullet-whitelist', help='Whitelist file', default='whitelist.txt')
    parser.add_argument('-dcwl', '--discord-whitelist', help='Whitelist file', default='whitelist.txt')
    parser.add_argument('-lat', '--latitude', help='Latitude which will be used to determine distance to pokemons', type=float)
    parser.add_argument('-lon', '--longitude', help='Longitude which will be used to determine distance to pokemons', type=float)
    parser.add_argument('-loc', '--location', help='Location. Latitude,Longitude format')
    parser.add_argument('-pb', '--pushbullet', help='Set if pushbullet should be notified')
    parser.add_argument('-dc', '--discord', help='Set if discord should be notified')
    args = parser.parse_args()

    if args.location:
        split = args.location.split(',')
        args.latitude = split[0]
        args.longitude = split[1]

    if 'PUSHBULLET_API_KEY' in os.environ:
        PUSHBULLET_API_KEY = os.environ['PUSHBULLET_API_KEY']
    if 'DISCORD_CHANNEL_ID' in os.environ and 'DISCORD_TOKEN' in os.environ:
        DISCORD_CHANNEL_ID = os.environ['DISCORD_CHANNEL_ID']
        DISCORD_TOKEN = os.environ['DISCORD_TOKEN']

    # Define methods that will notify different services
    notify_methods = []

    if args.pushbullet:
        print "Notifying to pushbullet"
        notify_methods.append((notify_pushbullet, {'PUSHBULLET_API_KEY': PUSHBULLET_API_KEY}))

    if args.discord:
        print "Notifying to discord"
        notify_methods.append((notify_discord, {'DISCORD_CHANNEL_ID': DISCORD_CHANNEL_ID, 'DISCORD_TOKEN': DISCORD_TOKEN}))

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

    global thresholds
    global whitelists

    if args.pushbullet_whitelist:
        ths, wl = get_thresholds_and_whitelist(args.pushbullet_whitelist)
        whitelists['pushbullet'] = wl
        thresholds['pushbullet'] = ths

    if args.discord_whitelist:
        ths, wl = get_thresholds_and_whitelist(args.discord_whitelist)
        whitelists['discord'] = wl
        thresholds['discord'] = ths

    # Start the server
    server = NotifierServer(args.host, args.port, args.latitude, args.longitude, whitelists, notifier_queue)
    server.run()


if __name__ == '__main__':
    main()

