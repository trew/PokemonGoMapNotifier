import json
import datetime
import requests
import logging
import gpxpy.geo
import math

log = logging.getLogger(__name__)


def get_pokemon_name(pokemon_id):
    if not hasattr(get_pokemon_name, 'names'):
        with open('data/names.json', 'r') as f:
            get_pokemon_name.names = json.load(f)

    return get_pokemon_name.names.get(str(pokemon_id), 'unknown')


def get_pokemon_id(pokemon_name):
    if not hasattr(get_pokemon_id, 'ids'):
        if not hasattr(get_pokemon_name, 'names'):
            get_pokemon_name(1) # initialize it

        get_pokemon_id.ids = {}
        for id, name in get_pokemon_name.names.iteritems():
            get_pokemon_id.ids[name] = str(id)

    return get_pokemon_id.ids.get(pokemon_name, '-1')


def get_move_name(move_id):
    if not hasattr(get_move_name, 'names'):
        with open('data/moves.json', 'r') as f:
            get_move_name.names = json.load(f)

    return get_move_name.names.get(str(move_id), 'unknown')


def get_team_name(team_id):
    if team_id == 0:
        return "Neutral"
    if team_id == 1:
        return "Mystic"
    if team_id == 2:
        return "Valor"
    if team_id == 3:
        return "Instinct"

    return None


def get_time_left(time):
    tth = datetime.datetime.fromtimestamp(time) - datetime.datetime.now()
    seconds = tth.total_seconds()
    minutes, seconds = divmod(seconds, 60)

    return u"%02d:%02d" % (minutes, seconds)


def get_readable_time(time):
    return datetime.datetime.fromtimestamp(time).strftime('%H:%M')


def get_google_maps(latitude, longitude):
    return "https://www.google.com/maps/place/{},{}".format(latitude, longitude)


def get_gamepress(pokemon_id):
    return "https://pokemongo.gamepress.gg/pokemon/{}".format(pokemon_id)


def get_static_google_maps(latitude, longitude, api_key, width=300, height=180, zoom=14):
    url = "https://maps.googleapis.com/maps/api/staticmap?markers={},{}&zoom={}&size={}x{}".format(
        latitude, longitude, zoom, width, height)

    if api_key is not None:
        url += "&key=%s" % api_key

    return url


def get_sublocality(latitude, longitude, api_key):
    if not api_key:
        return None

    base = "https://maps.googleapis.com/maps/api/geocode/json?"
    params = "latlng={lat},{lon}&sensor={sen}&key={api_key}".format(
        lat=latitude,
        lon=longitude,
        sen='true',
        api_key=api_key
    )
    url = "{base}{params}".format(base=base, params=params)
    try:
        response = requests.get(url)
    except requests.exceptions.RequestException as e:
        log.exception("Error fetching sublocality")
        return None

    if not response.ok:
        log.error("Error in response when fetching sublocality: %s", str(response))
        return None

    for result in response.json()['results']:
        if 'address_components' in result:
            address_components = result['address_components']

            for address in address_components:
                address_types = address['types']

                if 'sublocality' in address_types:
                    return address['long_name']

    return None


def get_distance(lat1, lon1, lat2, lon2):
    return int(gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2))


def get_stats(pokemon_id):
    if not hasattr(get_pokemon_name, 'stats'):
        with open('data/stats.json', 'r') as f:
            get_stats.stats = json.load(f)

    return get_stats.stats.get(str(pokemon_id))


def get_cpm_for_level(level):
    if not hasattr(get_cpm_for_level, 'cpm'):
        with open('data/cpm.json', 'r') as f:
            get_cpm_for_level.cpm = json.load(f)

    return get_cpm_for_level.cpm.get(str(level))


def get_level_from_cpm(cpm_in):
    if not hasattr(get_level_from_cpm, 'levels'):
        if not hasattr(get_cpm_for_level, 'cpm'):
            get_cpm_for_level(1)

    cpm_in = str(cpm_in)
    max_length = 5

    if len(cpm_in) > max_length:
        cpm_in = cpm_in[:max_length]

    level_to_cpm = {}
    for level,cpm in get_cpm_for_level.cpm.iteritems():
        cpm_cmp = str(cpm)[:max_length]
        level_to_cpm[cpm_cmp] = level

    return int(level_to_cpm.get(cpm_in, '-1'))


def get_cp_for_level(pokemon_id, level, iv_attack, iv_defense, iv_stamina):
    stats = get_stats(pokemon_id)
    attack = stats.get('attack') + iv_attack
    defense = stats.get('defense') + iv_defense
    stamina = stats.get('stamina') + iv_stamina

    cp_multiplier = get_cpm_for_level(level)

    cp = attack * math.sqrt(defense) * math.sqrt(stamina) * (math.pow(cp_multiplier, 2) / float(10))

    return int(math.floor(cp))


def get_hp_for_level(pokemon_id, level, iv_stamina):
    stats = get_stats(pokemon_id)
    stamina = stats.get('stamina') + iv_stamina

    cp_multiplier = get_cpm_for_level(level)

    hp = stamina * cp_multiplier

    return int(math.floor(hp))


def is_inside_polygon(polygon, x, y):
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside
