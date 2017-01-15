import pgoapi
import pgoapi.utilities
import datetime
import time
import logging
import requests
import base64
import notifier.utils

log = logging.getLogger(__name__)

captcha_key = None
hash_key = None

accounts = []


def configure(captcha, hash, accs):
    global captcha_key, hash_key
    captcha_key = captcha
    hash_key = hash
    for acc in accs:
        if 'username' in acc and 'password' in acc:
            add_account(acc['username'], acc['password'])


def add_account(username, password):
    account = {
        'username': username,
        'password': password,
        'last_scan': None
    }
    accounts.append(account)


def get_account():
    global accounts
    accounts = sorted(accounts, key=lambda x: x['last_scan'] if x['last_scan'] is not None else datetime.datetime.utcfromtimestamp(0))

    now = datetime.datetime.utcnow()
    for acc in accounts:
        last_scan = acc['last_scan']
        if last_scan is None:
            return acc

        time_since = now - last_scan

        if time_since > datetime.timedelta(minutes=10):
            return acc

    return None


def get_api():
    if not hasattr(get_api, 'api'):
        api = pgoapi.PGoApi()
        if hash_key is None:
            raise RuntimeError('Hash key must be provided the first time get_api is called')
        api.activate_hash_server(hash_key)
        get_api.api = api

    return get_api.api


def get_map_objects_with_retries(location, username, retry_count, expected_pokemon=False):
    i = 0
    while i < retry_count:
        if i > 0:
            time.sleep(10)
        i += 1
        response_dict = get_map_objects(location, username)

        if response_dict is None:
            log.warn('get_map_objects returned an empty response, trying again in 10 seconds')
            continue

        # Ok we have some map object data, lets parse it
        # parsed = parse_map(args, response_dict, step_location, dbq, whq, api, scan_date)

        nearby_pokemons = []
        wild_pokemons = []
        pokestops_and_gyms = []

        cells = response_dict['responses']['GET_MAP_OBJECTS']['map_cells']
        for cell in cells:
            nearby_pokemons += cell.get('nearby_pokemons', [])
            wild_pokemons += cell.get('wild_pokemons', [])
            pokestops_and_gyms += cell.get('forts', [])

        if not wild_pokemons and not nearby_pokemons and not pokestops_and_gyms:
            log.warn('Literally nothing was returned')
            continue

        if expected_pokemon and not wild_pokemons:
            log.warn('No pokemons were returned even though some were expected')
            continue

        # return the response
        return {'nearby': nearby_pokemons,
                'wild': wild_pokemons,
                'forts': pokestops_and_gyms,
                'response': response_dict}


def scan(location, account, expected_pokemon=True):
    # make sure it's initialized with hash key
    get_api()

    # accept both dicts with 'lat','lon' and lists with two elements
    if isinstance(location, dict):
        if 'lat' in location and 'lon' in location:
            location = [location['lat'], location['lon']]
        else:
            raise RuntimeError("Unable to parse location parameter: %s", location)

    # login at location
    if not login(location, account['username'], account['password']):
        return None

    # request map objects
    map_dict = get_map_objects_with_retries(location, account['username'], 5, expected_pokemon=expected_pokemon)

    if map_dict is None:
        log.error('Unable to receive a response from location %s with %s in %s tries', location, account['username'], 5)

    return map_dict


def encounter(encounter_id, spawn_point_id, username, location, encounter_retries):
    api = get_api()
    i = 0
    while i < encounter_retries:
        if i > 0:
            time.sleep(1)
        i += 1

        req = api.create_request()

        req.encounter(encounter_id=encounter_id,
                      spawn_point_id=spawn_point_id,
                      player_latitude=location[0],
                      player_longitude=location[1])
        req.check_challenge()
        req.get_hatched_eggs()
        req.get_inventory()
        req.check_awarded_badges()
        req.download_settings()
        req.get_buddy_walked()
        encounter_result = check_and_resolve_recaptcha(req,
                                                       username,
                                                       encounter,
                                                       encounter_id,
                                                       spawn_point_id,
                                                       username,
                                                       location,
                                                       encounter_retries)

        if encounter_result is None:
            log.warn('No response from encounter request')
            continue

        status = encounter_result.get('responses', {}).get('ENCOUNTER', {}).get('status', -1)
        if status != 1:
            # something serious went wrong
            log.error("Error parsing response from encounter. Status: %s - %s", status, encounter_result)
            continue

        return encounter_result['responses']['ENCOUNTER']

    log.error('Unable to encounter pokemon %s in %s tries', encounter_id, encounter_retries)
    return None


def scan_and_encounter(location, pokemon_name):
    pokemon_id = int(notifier.utils.get_pokemon_id(pokemon_name.capitalize()))
    if pokemon_id <= 0:
        return 'Unable to resolve pokemon id for "%s"' % pokemon_name

    account = get_account()
    if account is None:
        log.error('No account available for scan')
        return 'No account available for scan'

    log.info('Attempting scan and encounter for %s at %s with %s', pokemon_name, location, account['username'])
    account['last_scan'] = datetime.datetime.utcnow()

    scan_data = scan(location, account, expected_pokemon=True)
    if scan_data is None:
        return 'Unable to scan location'
    time.sleep(1)

    wild = scan_data['wild']
    if not wild:
        return 'No wild pokemons found. Encounter not possible'

    encountered = []
    has_encountered = False
    for p in wild:
        if p['pokemon_data']['pokemon_id'] == pokemon_id:
            if has_encountered:
                time.sleep(2)
            has_encountered = True

            encounter_data = encounter(p['encounter_id'], p['spawn_point_id'], account['username'], location, 3)

            if encounter_data is None:
                encountered.append('Unable to encounter pokemon')
                continue

            encounter_data['wild_pokemon']['encounter_id'] = base64.b64encode(str(
                encounter_data['wild_pokemon']['encounter_id']))
            encounter_data['wild_pokemon']['pokemon_data']['level'] = notifier.utils.get_level_from_cpm(
                encounter_data['wild_pokemon']['pokemon_data']['cp_multiplier'])

            encountered.append(encounter_data)

    return encountered


def get_map_objects(location, username):
    api = get_api()
    try:
        cell_ids = pgoapi.utilities.get_cell_ids(location[0], location[1])
        timestamps = [0, ] * len(cell_ids)
        req = api.create_request()
        req.get_map_objects(latitude=pgoapi.utilities.f2i(location[0]),
                            longitude=pgoapi.utilities.f2i(location[1]),
                            since_timestamp_ms=timestamps,
                            cell_id=cell_ids)
        req.check_challenge()
        req.get_hatched_eggs()
        req.get_inventory()
        req.check_awarded_badges()
        req.download_settings()
        req.get_buddy_walked()
        return check_and_resolve_recaptcha(req, username, get_map_objects, location, username)

    except Exception as e:
        log.warning('Exception while downloading map: %s', e)


def login(location, username, password):
    """
    Code blatantly stolen and adapted from PokemonGo-Map
    """
    login_retries = 3
    login_delay = 5
    api = get_api()
    api.set_position(location[0], location[1], 35)

    # Logged in? Enough time left? Cool!
    if api._auth_provider and api._auth_provider._ticket_expire:
        remaining_time = api._auth_provider._ticket_expire / 1000 - time.time()
        if remaining_time > 60:
            log.debug('Credentials remain valid for another %f seconds.', remaining_time)
            return True

    # Try to login. Repeat a few times, but don't get stuck here.
    i = 0
    while i < login_retries:
        try:
            api.set_authentication(provider='ptc', username=username, password=password)
            break
        except pgoapi.exceptions.AuthException:
            if i >= login_retries:
                log.error('Exceeded login attempts')
                return False
            else:
                i += 1
                log.error('Failed to login to Pokemon Go with account %s. Trying again in %g seconds.', username,
                          login_delay)
                time.sleep(login_delay)

    log.debug('Login for account %s successful.', username)
    time.sleep(15)

    return True


def check_and_resolve_recaptcha(request, username, retry_function, *args, **kwargs):
    response = request.call()

    # Captcha check.
    captcha_url = response['responses']['CHECK_CHALLENGE']['challenge_url']
    if len(captcha_url) > 1:
        log.warn('Account %s is encountering a captcha, starting 2captcha sequence.', username)
        captcha_token = resolve_recaptcha(captcha_url)

        if 'ERROR' in captcha_token:
            log.error("Unable to resolve captcha for %s, please check your 2captcha API key and/or wallet balance.",
                      username)
            return None

        log.info('Retrieved captcha token, attempting to verify challenge for %s.', username)
        api = get_api()
        response = api.verify_challenge(token=captcha_token)

        if 'success' in response['responses']['VERIFY_CHALLENGE']:
            log.info('Account %s successfully uncaptcha\'d.', username)

            # Now try again
            return retry_function(*args, **kwargs)
        else:
            log.error('Account %s failed verifyChallenge', username)
            return None

    return response

    pass


def resolve_recaptcha(url):
    s = requests.Session()
    captcha_dsk = '6LeeTScTAAAAADqvhqVMhPpr_vB9D364Ia-1dSgK'
    # Fetch the CAPTCHA_ID from 2captcha.
    try:
        url = "http://2captcha.com/in.php?key={}&method=userrecaptcha&googlekey={}&pageurl={}".format(captcha_key,
                                                                                                      captcha_dsk,
                                                                                                      url)
        captcha_id = s.post(url).text.split('|')[1]
        captcha_id = str(captcha_id)
    # IndexError implies that the returned response was a 2captcha error.
    except IndexError:
        return 'ERROR'

    log.info('Retrieved captcha ID: %s; now retrieving token.', captcha_id)

    # Get the response, retry every 5 seconds if it's not ready.
    recaptcha_response = s.get(
        "http://2captcha.com/res.php?key={}&action=get&id={}".format(captcha_key, captcha_id)).text

    while 'CAPCHA_NOT_READY' in recaptcha_response:
        log.info("Captcha token is not ready, retrying in 5 seconds...")
        time.sleep(5)
        recaptcha_response = s.get(
            "http://2captcha.com/res.php?key={}&action=get&id={}".format(captcha_key, captcha_id)).text

    token = str(recaptcha_response.split('|')[1])
    return token
