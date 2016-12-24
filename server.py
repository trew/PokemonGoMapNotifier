#!/usr/bin/env python

import configargparse
import requests
import urllib
import os
import simplejson as json
from Queue import Queue
from threading import Thread
from cachetools import LRUCache
import gpxpy.geo
import BaseHTTPServer
import SocketServer
import pogoidmapper
import config
import datetime
import logging


class NotifierServer:
    def __init__(self, host, port, latitude, longitude, notifier_queue):
        self.host = host
        self.port = port
        self.latitude = latitude
        self.longitude = longitude
        self.notifier_queue = notifier_queue
        self.cache = LRUCache(maxsize=100)

    def sublocality(self, latitude, longitude):
        base = "http://maps.googleapis.com/maps/api/geocode/json?"
        params = "latlng={lat},{lon}&sensor={sen}".format(
						lat=latitude,
						lon=longitude,
						sen='true'
				)
        url = "{base}{params}".format(base=base, params=params)
        response = requests.get(url)

        for result in response.json()['results']:
            if 'address_components' in result:
                address_components = result['address_components']

                for address in address_components:
                    addressTypes = address['types']

                    if 'sublocality' in addressTypes:
                        return address['long_name']

        return ""

    def process(self, message):
        """
        Processes an encountered pokemon and determines whether to send a notification or not
        """
        accepted = False
        for whitelist in config.whitelists.values():
            if accept(message, whitelist):
                accepted = True
                break

        if not accepted:
            return

        pokemon_id = message['pokemon_id']
        pokemon_name = pogoidmapper.get_pokemon_name(pokemon_id)
        encounter = message['encounter_id']
        if encounter in self.cache:
            print "{} cached. Skipping notification. Encounter: {}".format(pokemon_name, encounter)
            return

        latitude = message['latitude']
        longitude = message['longitude']
        ivs = None
        moves = None
        if 'individual_attack' in message and message['individual_attack'] is not None:
            if ivs is None:
                ivs = [-1, -1, -1]
            ivs[0] = int(message['individual_attack'])
        if 'individual_defense' in message and message['individual_defense'] is not None:
            if ivs is None:
                ivs = [-1, -1, -1]
            ivs[1] = int(message['individual_defense'])
        if 'individual_stamina' in message and message['individual_stamina'] is not None:
            if ivs is None:
                ivs = [-1, -1, -1]
            ivs[2] = int(message['individual_stamina'])
        if 'move_1' in message and message['move_1'] is not None:
            if moves is None:
                moves = ["uk", "uk"]
            moves[0] = pogoidmapper.get_move_name(message['move_1'])
        if 'move_2' in message and message['move_2'] is not None:
            if moves is None:
                moves = ["uk", "uk"]
            moves[1] = pogoidmapper.get_move_name(message['move_2'])

        if encounter in self.cache:
            return
        self.cache[encounter] = 1  # cache it

        maps = "https://www.google.com/maps/place/{0},{1}".format(latitude, longitude)
        staticMaps = "https://maps.googleapis.com/maps/api/staticmap?markers={},{}&zoom=15&size=544x424".format(latitude, longitude)
        navigation = "https://maps.google.com/maps?saddr={0},{1}&daddr={2},{3}".format(self.latitude,
                                                                                      self.longitude,
                                                                                      latitude,
                                                                                      longitude)

        gamepress = "https://pokemongo.gamepress.gg/pokemon/{0}".format(pokemon_id)

        message.update({
            'gamepress': gamepress,
            'maps': maps,
            'staticMaps': staticMaps,
            'sublocality': self.sublocality(latitude, longitude),
            'navigation': navigation,
            'ivs': ivs,
            'moves': moves
        })
        self.notifier_queue.put(message)

    def run(self):
        handler = ServerHandler
        httpd = SocketServer.TCPServer((self.host, self.port), handler)
        httpd.notifier_server = self

        print "Serving at: http://{}:{}".format(self.host, self.port)
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
        Processes encountered pokemons, and sends them over to the notifier server
        """

        if self.headers['content-type'] == 'application/json':
            data_string = self.rfile.read(int(self.headers['content-length']))
            data = json.loads(data_string)
            type = data['type']

            # only check pokemon type
            if type == 'pokemon':
                message = data['message']
                pokemon_id = message['pokemon_id']

                latitude = message['latitude']
                longitude = message['longitude']

                has_distance = self.server.notifier_server.latitude and self.server.notifier_server.longitude
                distance = get_distance(float(self.server.notifier_server.latitude),
                                        float(self.server.notifier_server.longitude),
                                        float(latitude),
                                        float(longitude)) if has_distance else None

                message.update({
                    'pokemon_id': int(message['pokemon_id']),
                    'name': pogoidmapper.get_pokemon_name(pokemon_id),
                    'distance': distance,
                })

                self.server.notifier_server.process(message)

        self.send_response(200)
        self.end_headers()


def get_simple_formatting(message):
    """
    Processes an encountered pokemon and determines whether to send a notification or not
    """

    pokemon_name = message['name']
    distance = message['distance']
    ivs = message['ivs']
    moves = message['moves']
    gamepress = message['gamepress']
    maps = message['maps']
    sublocality = message['sublocality']
    navigation = message['navigation']
    disappear_time = message['disappear_time']

    disappear_datetime = datetime.datetime.fromtimestamp(disappear_time)
    # now = datetime.datetime.fromtimestamp(disappear_time - 60 * 30)
    now = datetime.datetime.now()

    tth = disappear_datetime - now
    seconds = tth.total_seconds()
    minutes, seconds = divmod(seconds, 60)
    tth_str = "%02d:%02d" % (minutes, seconds)

    extra_str = ""
    if ivs and moves:
        iv_percent = int((float(ivs[0]) + float(ivs[1]) + float(ivs[2])) / 45 * 100)
        extra_str = "IV: {}/{}/{} {}%\nMoves:\n* {}\n* {}\n{}".format(ivs[0],
                                                                      ivs[1],
                                                                      ivs[2],
                                                                      iv_percent,
                                                                      moves[0],
                                                                      moves[1],
                                                                      gamepress)

    distance_str = "Distance is {}m.".format(distance) if distance else ""

    maps = "Google Maps: {}{}".format(maps, " in " + sublocality if sublocality != "" else "") if maps else ""
    navigation = "Navigation: {}".format(navigation) if navigation else ""

    if ivs and sum(ivs) == 45:
        title = "Perfect "
    title = "{} found! Time left: {}".format(pokemon_name, tth_str)
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


def notify_simple(message):
    title, body = get_simple_formatting(message)
    print "{}\n{}".format(title, body)


def notify_pushbullet(message):
    ivs = message['ivs']
    pokemon_id = message['pokemon_id']
    distance = message['distance']

    perfect_ivs = sum(ivs) == 45 if ivs else False
    anti_perfect_ivs = sum(ivs) == 0 if ivs else False

    if not (perfect_ivs or anti_perfect_ivs):
        if pokemon_id not in config.whitelists['pushbullet']:
            return

        threshold = config.thresholds['pushbullet'][pokemon_id]

        if distance and 0 < threshold < distance:
            # pokemon is out of range
            return

    title, body = get_simple_formatting(message['name'], message['distance'], message['ivs'], message['moves'],
                                        message['gamepress'], message['maps'], message['navigation'], message['sublocality'])

    url = 'https://api.pushbullet.com/v2/pushes'
    headers = {'Content-type': 'application/x-www-form-urlencoded'}
    session = requests.Session()
    session.auth = (config.PUSHBULLET_API_KEY, '')
    session.headers.update(headers)
    body = {
        'type': 'note',
        'title': title,
        'body': body,
    }

    body = urllib.urlencode(body)
    if send(session, url, body):
        print 'Pushbullet message sent: ' + title


def accept(message, whitelist):
    ivs = None
    if message.get('individual_attack'):
        ivs = [int(message['individual_attack']), int(message['individual_defense']),
               int(message['individual_stamina'])]

    cp = message.get('cp')
    pokemon_name = pogoidmapper.get_pokemon_name(str(message['pokemon_id']))
    quick_move = pogoidmapper.get_move_name(message['move_1']) if 'move_1' in message else None
    charge_move = pogoidmapper.get_move_name(message['move_2']) if 'move_2' in message else None

    perfect_ivs = sum(ivs) == 45 if ivs else False
    anti_perfect_ivs = sum(ivs) == 0 if ivs else False

    notify_on_perfect_iv = whitelist.get('config', {}).get('notify_on_perfect_iv', False)
    notify_on_zero_iv = whitelist.get('config', {}).get('notify_on_zero_iv', False)
    if notify_on_perfect_iv and perfect_ivs:
        return True
    if notify_on_zero_iv and anti_perfect_ivs:
        return True

    include = whitelist.get('include', [])
    exclude = whitelist.get('exclude', [])  # todo, not supported yet
    for element in include:
        if pokemon_name != element.get('name', None):
            continue
        if 'max_cp' in element and (not cp or cp > element.get('max_cp', 9999)):
            continue
        if 'min_cp' in element and (not cp or cp < element.get('min_cp', 0)):
            continue
        if 'quick_move' in element and quick_move != element.get('quick_move'):
            continue
        if 'charge_move' in element and charge_move != element.get('charge_move'):
            continue

        return True


def notify_discord(message):
    whitelist = config.whitelists['discord']
    if not accept(message, whitelist):
        return
    ivs = message.get('ivs')
    moves = message.get('moves')

    perfect_ivs = sum(ivs) == 45 if ivs else False
    anti_perfect_ivs = sum(ivs) == 0 if ivs else False

    if perfect_ivs:
        body = "Perfect "
    elif anti_perfect_ivs:
        body = "Shittiest possible "
    else:
        body = ""

    disappear_time = message['disappear_time']

    disappear_datetime = datetime.datetime.fromtimestamp(disappear_time)
    # now = datetime.datetime.fromtimestamp(disappear_time - 60 * 30)
    now = datetime.datetime.now()

    tth = disappear_datetime - now
    seconds = tth.total_seconds()
    minutes, seconds = divmod(seconds, 60)
    tth_str = "%02d:%02d" % (minutes, seconds)
    time_str = "Disappears in: {} (**{}**)".format(tth_str, disappear_datetime.strftime('%H:%M:%S'))

    body += "**{}** found{}!\n\n{}".format(message['name'], " in **" + message['sublocality'] + "**" if message['sublocality'] != "" else "", time_str)
    extra_str = ""
    if ivs and moves:
        iv_percent = int((float(ivs[0]) + float(ivs[1]) + float(ivs[2])) / 45 * 100)
        extra_str = "\n\nIV: {}/{}/{} **{}%**\nMoves: {} - {}.\n\n".format(ivs[0],
                                                                   ivs[1],
                                                                   ivs[2],
                                                                   iv_percent,
                                                                   moves[0],
                                                                   moves[1])
    else:
        discord_log.warn("IVs: {} Moves: {} ExtraStr: {}".format(ivs, moves, extra_str))
        discord_log.warn(str(message))
    body += extra_str
    body += "{}\n\n{}\n\n{}".format(message['gamepress'], message['maps'], message['staticMaps'])

    channel = config.DISCORD_CHANNEL_ID
    token = config.DISCORD_TOKEN
    url = 'https://discordapp.com/api/webhooks/{}/{}'.format(channel, token)
    headers = {'Content-type': 'application/json'}

    session = requests.Session()
    session.headers.update(headers)
    body = {
        'content': body
    }

    body = json.dumps(body)
    discord_log.info('Discord notified: ' + body)
    if send(session, url, body):
        discord_log.info(body)
        body = body[13:body.find("found!")]
        print 'Discord notified: ' + body


def notifier(methods, q):
    while True:
        try:
            while True:
                message = q.get()
                for method in methods:
                    try:
                        method(message)
                    except Exception as e1:
                        print "Exception in notifier({}): {}".format(method.__name__, e1)
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


discord_log = logging.getLogger('discord')


def main():
    logging.basicConfig(filename='log.txt', level=10) # debug logging
    global discord_log
    discord_log = logging.getLogger('discord')

    parser = configargparse.ArgParser()
    parser.add_argument('--host', help='Host', default='localhost')
    parser.add_argument('-p', '--port', help='Port', type=int, default=8000)
    parser.add_argument('-lat', '--latitude', help='Latitude which will be used to determine distance to pokemons',
                        type=float)
    parser.add_argument('-lon', '--longitude', help='Longitude which will be used to determine distance to pokemons',
                        type=float)
    parser.add_argument('-loc', '--location', help='Location. Latitude,Longitude format')
    parser.add_argument('-pb', '--pushbullet', help='Set if pushbullet should be notified')
    parser.add_argument('-dc', '--discord', help='Set if discord should be notified')
    args = parser.parse_args()

    if args.location:
        split = args.location.split(',')
        args.latitude = split[0]
        args.longitude = split[1]

    # Define methods that will notify different services
    notify_methods = []

    if args.pushbullet:
        print "Notifying to pushbullet"
        notify_methods.append(notify_pushbullet)

    if args.discord:
        print "Notifying to discord"
        notify_methods.append(notify_discord)

    if not notify_methods:
        print "Printing simple notifications"
        notify_methods.append(notify_simple)

    # set up the notification thread
    notifier_queue = Queue()
    t = Thread(target=notifier,
               name='Notifier',
               args=(notify_methods, notifier_queue))
    t.daemon = True
    t.start()

    # Start the server
    server = NotifierServer(args.host, args.port, args.latitude, args.longitude, notifier_queue)
    server.run()


if __name__ == '__main__':
    main()
