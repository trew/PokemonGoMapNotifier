import json
import datetime
import requests
import logging
import gpxpy.geo

log = logging.getLogger(__name__)


def get_pokemon_name(id):
    if not hasattr(get_pokemon_name, 'names'):
        with open('data/names.json', 'r') as f:
            get_pokemon_name.names = json.load(f)

    return get_pokemon_name.names.get(str(id), 'unknown').encode('utf-8')


def get_move_name(id):
    if not hasattr(get_move_name, 'names'):
        with open('data/moves.json', 'r') as f:
            get_move_name.names = json.load(f)

    return get_move_name.names.get(str(id), 'unknown').encode('utf-8')


def get_time_left(disappear_time):
    tth = datetime.datetime.fromtimestamp(disappear_time) - datetime.datetime.now()
    seconds = tth.total_seconds()
    minutes, seconds = divmod(seconds, 60)

    return u"%02d:%02d" % (minutes, seconds)


def get_disappear_time(disappear_time):
    return datetime.datetime.fromtimestamp(disappear_time).strftime('%H:%M')


def get_google_maps(latitude, longitude, shorten=False, api_key=None):
    url = "https://www.google.com/maps/place/{},{}".format(latitude, longitude)
    return shorten_url(url, api_key) if shorten and api_key else url


def get_gamepress(pokemon_id, shorten=False, api_key=None):
    url = "https://pokemongo.gamepress.gg/pokemon/{}".format(pokemon_id)
    return shorten_url(url, api_key, cache=True) if shorten and api_key else url


def get_static_google_maps(latitude, longitude, shorten=False, api_key=None, width=300, height=180, zoom=14):
    url = "https://maps.googleapis.com/maps/api/staticmap?markers={},{}&zoom={}&size={}x{}".format(
        latitude,
        longitude, zoom, width, height)
    return shorten_url(url, api_key) if shorten and api_key else url


def shorten_url(url, api_key, cache=False):
    if cache:
        if not hasattr(shorten_url, 'cache'):
            shorten_url.cache = {}
        if url in shorten_url.cache:
            log.debug("Returning cached short url for %s" % url)
            return shorten_url.cache[url]

    post_url = 'https://www.googleapis.com/urlshortener/v1/url?key={}'.format(api_key)
    payload = {'longUrl': url}
    r = requests.post(post_url, data=json.dumps(payload), headers={'content-type': 'application/json'})
    if r.ok:
        shortened = r.json()['id']
        if cache:
            log.debug("Caching short url for %s" % url)
            shorten_url.cache[url] = shortened

        return shortened

    log.warn("Unable to shorten url")
    return url


def get_sublocality(latitude, longitude, api_key):
    if not api_key:
        return None

    base = "http://maps.googleapis.com/maps/api/geocode/json?"
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
