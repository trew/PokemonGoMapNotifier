from threading import Thread
from .utils import *
import logging
import Queue
import commentjson as json

log = logging.getLogger(__name__)


class Notifier(Thread):
    """
    Receives data from the webserver and deals with it.
    """

    def __init__(self, config_file):
        super(Notifier, self).__init__()

        self.daemon = True
        self.name = "Notifier"
        self.notification_handlers = {}
        self.processed_pokemons = {}
        self.processed_raids = {}
        self.latitude, self.longitude = None, None
        self.gyms = {}

        self.queue = Queue.Queue()

        if isinstance(config_file, str):
            with open(config_file) as f:
                log.info('Loading %s', config_file)
                parsed = json.load(f)
        elif isinstance(config_file, dict):
            parsed = config_file
        else:
            raise RuntimeError('Unexpected parameter type: %s' % config_file)

        log.debug('Parsing "config"')
        config = parsed.get('config', {})
        self.google_key = config.get('google_key')
        self.fetch_sublocality = config.get('fetch_sublocality', False)
        self.shorten_urls = config.get('shorten_urls', False)

        self.endpoints = parsed.get('endpoints', {})
        self.trainers = parsed.get('trainers', [])

        from .simple import Simple
        self.notification_handlers['simple'] = Simple()

        for endpoint in self.endpoints:
            endpoint_type = self.endpoints[endpoint].get('type')
            if endpoint_type == 'discord' and 'discord' not in self.notification_handlers:
                log.info('Adding Discord to available notification handlers')
                from .discord import Discord
                self.notification_handlers['discord'] = Discord()

        self.includes = parsed.get('includes', {})

        # filter out disabled notifiers
        parsed_notification_settings = parsed.get('notification_settings', {})
        self.notification_settings = {k: v for k, v in parsed_notification_settings.items() if v.get('enabled', True)}

        self.parse_includes()

        self.includes_to_notifications = {}
        self.raid_includes_to_notifications = {}
        active_includes = set()

        # loop through all notification settings
        for notification_setting in self.notification_settings:

            # get all include references for this notification setting
            for include in self.notification_settings[notification_setting].get('includes', []):
                if include not in self.includes_to_notifications:
                    self.includes_to_notifications[include] = []

                # mark this include as active and create the link between includes and notifications
                active_includes.add(include)
                self.includes_to_notifications[include].append(notification_setting)

            # get all raid references for this notification setting
            for raid_include in self.notification_settings[notification_setting].get('raids', []):
                if raid_include not in self.raid_includes_to_notifications:
                    self.raid_includes_to_notifications[raid_include] = []

                # mark this include as active and create the link between includes and notifications
                active_includes.add(raid_include)
                self.raid_includes_to_notifications[raid_include].append(notification_setting)

        # remove includes that's not used by any notifications
        self.includes = {k: v for k, v in self.includes.items() if k in active_includes}

        if not self.includes:
            raise RuntimeError('No includes configured')

        # remove includes refs, because they are not needed. simplifies debugging
        for notification_setting in self.notification_settings:
            # these references are covered by another dict, namely self.includes_to_notifications
            self.notification_settings[notification_setting].pop('includes', None)

            # if it's still here, it's enabled
            self.notification_settings[notification_setting].pop('enabled', None)

        # log some debug info
        for include,notification_setting_refs in self.includes_to_notifications.iteritems():
            log.debug('Notifying %s to %s', include, notification_setting_refs)

        log.info('Initialized')

    def parse_includes(self):
        self.resolve_configurations()
        self.resolve_refs()

        # bring the 'pokemons' entry to root level
        for include in self.includes:
            self.includes[include] = self.includes[include]['pokemons']

    def resolve_refs(self):
        for include in self.includes:
            include = self.includes[include]
            if 'pokemons' not in include:
                include['pokemons'] = []

            for ref in include.get('pokemons_refs', []):
                self.add_pokemons_from_ref(ref, include)

            include.pop('pokemons_refs', None)
            self.resolve_configurations()

    def add_pokemons_from_ref(self, ref, include):
        resolved_ref = self.includes.get(ref)

        if 'pokemons' in resolved_ref:
            for pokemon in resolved_ref['pokemons']:
                include['pokemons'].append(pokemon.copy())

        if 'pokemons_refs' in resolved_ref:
            for r in resolved_ref['pokemons_refs']:
                self.add_pokemons_from_ref(r, include)

    def resolve_configurations(self):
        for include in self.includes:
            include = self.includes[include]

            for pokemon in include.get('pokemons', []):
                self.add_if_missing('min_id', include, pokemon)
                self.add_if_missing('max_id', include, pokemon)
                self.add_if_missing('min_iv', include, pokemon)
                self.add_if_missing('max_iv', include, pokemon)
                self.add_if_missing('min_cp', include, pokemon)
                self.add_if_missing('max_cp', include, pokemon)
                self.add_if_missing('min_hp', include, pokemon)
                self.add_if_missing('max_hp', include, pokemon)
                self.add_if_missing('min_attack', include, pokemon)
                self.add_if_missing('max_attack', include, pokemon)
                self.add_if_missing('min_defense', include, pokemon)
                self.add_if_missing('max_defense', include, pokemon)
                self.add_if_missing('min_stamina', include, pokemon)
                self.add_if_missing('max_stamina', include, pokemon)
                self.add_if_missing('min_lat', include, pokemon)
                self.add_if_missing('max_lat', include, pokemon)
                self.add_if_missing('min_lon', include, pokemon)
                self.add_if_missing('max_lon', include, pokemon)
                self.add_if_missing('name', include, pokemon)
                self.add_if_missing('max_dist', include, pokemon)
                self.add_if_missing('moves', include, pokemon)
                self.add_if_missing('level30cp', include, pokemon)

    @staticmethod
    def add_if_missing(key, source, target):
        if key in source and key not in target:
            target[key] = source[key]

    def run(self):
        log.info('Notifier thread started.')

        while True:
            for i in range(0, 5000):
                data = self.queue.get(block=True)

                message_type = data.get('type')

                if message_type == 'pokemon':
                    self.handle_pokemon(data['message'])
                elif message_type == 'gym_details':
                    self.handle_gym_details(data['message'])
                elif message_type == 'raid':
                    self.handle_raid(data['message'])
                else:
                    log.debug('Unsupported message type: %s', message_type)
            self.clean()

    def clean(self):
        now = datetime.datetime.utcnow()
        remove = []

        for encounter_id in self.processed_pokemons:
            if self.processed_pokemons[encounter_id] < now:
                remove.append(encounter_id)
        for encounter_id in remove:
            del self.processed_pokemons[encounter_id]

        remove = []
        for key in self.processed_raids:
            if self.processed_raids[key] < now:
                remove.append(key)
        for key in remove:
            del self.processed_raids[key]

    def set_notification_handler(self, name, handler):
        self.notification_handlers[name] = handler

    @staticmethod
    def check_min(config_key, included_pokemon, message_key, pokemon, match_data):
        required_value = included_pokemon.get(config_key)
        if required_value is None:
            return True

        pokemon_value = pokemon.get(message_key, -1)
        if pokemon_value < required_value:
            return False

        match_data.append(config_key)
        return True

    @staticmethod
    def check_max(config_key, included_pokemon, message_key, pokemon, match_data):
        required_value = included_pokemon.get(config_key)
        if required_value is None:
            return True

        pokemon_value = pokemon.get(message_key, 99999)
        if pokemon_value > required_value:
            return False

        match_data.append(config_key)
        return True

    @staticmethod
    def check_min_max(key, included_pokemon, pokemon, match_data):
        """
        Returns True if included_pokemon matches the given pokemon
        """
        check_min = Notifier.check_min('min_' + key, included_pokemon, key, pokemon, match_data)
        check_max = Notifier.check_max('max_' + key, included_pokemon, key, pokemon, match_data)
        return check_min and check_max

    def matches(self, pokemon, pokemon_rules):
        match_data = []

        # check name. if name specification doesn't exist, it counts as valid
        name = pokemon_rules.get('name')
        if name is not None:
            if name != pokemon['name']:
                return False, None
            else:
                match_data.append('name')

        # check latitude
        if not Notifier.check_min_max('lat', pokemon_rules, pokemon, match_data):
            return False, None

        # check longitude
        if not Notifier.check_min_max('lon', pokemon_rules, pokemon, match_data):
            return False, None

        # check id
        if not Notifier.check_min_max('id', pokemon_rules, pokemon, match_data):
            return False, None

        # check iv
        if not Notifier.check_min_max('iv', pokemon_rules, pokemon, match_data):
            return False, None

        # check attack
        if not Notifier.check_min_max('attack', pokemon_rules, pokemon, match_data):
            return False, None

        # check defense
        if not Notifier.check_min_max('defense', pokemon_rules, pokemon, match_data):
            return False, None

        # check stamina
        if not Notifier.check_min_max('stamina', pokemon_rules, pokemon, match_data):
            return False, None

        # check level (raids)
        if not Notifier.check_min_max('level', pokemon_rules, pokemon, match_data):
            return False, None

        # check cp at level
        min_cp = pokemon_rules.get('min_cp')
        if min_cp is not None:
            if 'attack' not in pokemon or 'defense' not in pokemon or 'stamina' not in pokemon:
                return False, None

            for level in min_cp:
                required_cp = min_cp[level]
                cp = get_cp_for_level(pokemon['id'], int(level), pokemon['attack'], pokemon['defense'],
                                      pokemon['stamina'])
                if cp < required_cp:
                    return False, None

            match_data.append('min_cp')

        max_cp = pokemon_rules.get('max_cp')
        if max_cp is not None:
            if 'attack' not in pokemon or 'defense' not in pokemon or 'stamina' not in pokemon:
                return False, None

            for level in max_cp:
                required_cp = max_cp[level]
                cp = get_cp_for_level(pokemon['id'], level, pokemon['attack'], pokemon['defense'], pokemon['stamina'])
                if cp < required_cp:
                    return False, None

            match_data.append('max_cp')

        # check hp at level
        min_hp = pokemon_rules.get('min_hp')
        if min_hp is not None:
            if 'stamina' not in pokemon:
                return False, None

            for level in min_hp:
                required_hp = min_hp[level]
                hp = get_hp_for_level(pokemon['id'], int(level), pokemon['stamina'])
                if hp < required_hp:
                    return False, None

            match_data.append('min_hp')

        max_hp = pokemon_rules.get('max_hp')
        if max_hp is not None:
            if 'stamina' not in pokemon:
                return False, None

            for level in max_hp:
                required_hp = max_hp[level]
                hp = get_hp_for_level(pokemon['id'], level, pokemon['stamina'])
                if hp < required_hp:
                    return False, None

            match_data.append('max_hp')

        # check distance
        max_dist = pokemon_rules.get('max_dist')
        if max_dist is not None:
            if self.longitude is None or self.latitude is None:
                return False, None

            distance = get_distance(self.latitude, self.longitude, pokemon['lat'], pokemon['lon'])
            if distance > max_dist:
                return False, None

            match_data.append('max_dist')

        # check moves
        if 'moves' in pokemon_rules:
            moves = pokemon_rules['moves']
            moves_match = False
            for move_set in moves:
                move_1 = move_set.get('move_1')
                move_2 = move_set.get('move_2')
                move_1_match = move_1 is None or move_1 == pokemon.get('move_1')
                move_2_match = move_2 is None or move_2 == pokemon.get('move_2')
                if move_1_match and move_2_match:
                    moves_match = True
                    break
            if not moves_match:
                return False, None

            match_data.append('moves')

        # Passed all checks. This pokemon matches!
        return True, match_data

    def is_included_pokemon(self, pokemon, included_list):
        matched = False
        for included_pokemon in included_list:
            match = self.matches(pokemon, included_pokemon)
            if match[0]:
                log.info(u"Found match for {} with rules: {}".format(pokemon['name'], match[1]))
                matched = True

        return matched

    def handle_pokemon(self, message):
        if message['encounter_id'] in self.processed_pokemons:
            log.debug('Encounter ID %s already processed.', message['encounter_id'])
            return

        self.processed_pokemons[message['encounter_id']] = datetime.datetime.utcfromtimestamp(message['disappear_time'])

        # initialize the pokemon dict
        pokemon = {
            'id': message['pokemon_id'],
            'name': get_pokemon_name(message['pokemon_id']),
            'lat': message['latitude'],
            'lon': message['longitude'],
            'cp': message['cp']
        }

        if 'pokemon_level' in message:
            pokemon['level'] = message['pokemon_level']

        # calculate IV if available and add corresponding values to the pokemon dict
        attack = int(message.get('individual_attack') if message.get('individual_attack') is not None else -1)
        defense = int(message.get('individual_defense') if message.get('individual_defense') is not None else -1)
        stamina = int(message.get('individual_stamina') if message.get('individual_stamina') is not None else -1)
        if attack > -1 and defense > -1 and stamina > -1:
            iv = float((attack + defense + stamina) * 100 / float(45))
            pokemon['attack'] = attack
            pokemon['defense'] = defense
            pokemon['stamina'] = stamina
            pokemon['iv'] = iv

        # add moves to pokemon dict if found
        move_1, move_2 = None, None
        if message.get('move_1') is not None:
            move_1 = get_move_name(message['move_1'])
        if message.get('move_2') is not None:
            move_2 = get_move_name(message['move_2'])

        if move_1 is not None:
            pokemon['move_1'] = move_1
        if move_2 is not None:
            pokemon['move_2'] = move_2

        to_notify = set([])

        # Loop through all active includes and send notifications if appropriate
        for include_ref in self.includes:
            include = self.includes.get(include_ref)
            match = self.is_included_pokemon(pokemon, include)

            if match:
                notification_setting_refs = self.includes_to_notifications.get(include_ref)

                if notification_setting_refs is not None:
                    for notification_setting_ref in notification_setting_refs:
                        to_notify.add(notification_setting_ref)
            else:
                log.debug('No match for %s in %s', pokemon['name'], include_ref)

        if to_notify:
            log.info('Notifying to %s', to_notify)
            for notification_setting_ref in to_notify:
                notification_setting = self.notification_settings.get(notification_setting_ref)
                self.notify(pokemon, message, notification_setting)

    def notify(self, pokemon, message, notification_setting):
        # find the handler and notify
        lat = message['latitude']
        lon = message['longitude']
        data = {
            'encounter_id': message['encounter_id'],
            'time': get_readable_time(message['disappear_time']),
            'time_left': get_time_left(message['disappear_time']),
            'google_maps': get_google_maps(lat, lon),
            'static_google_maps': get_static_google_maps(lat, lon, self.google_key),
            'gamepress': get_gamepress(message['pokemon_id'])
        }
        pokemon.update(data)

        # add sublocality
        if self.fetch_sublocality and 'sublocality' not in pokemon:
            if not self.google_key:
                log.warn('You must provide a google api key in order to fetch sublocality')
                pokemon['sublocality'] = None
            else:
                pokemon['sublocality'] = get_sublocality(pokemon['lat'], pokemon['lon'], self.google_key)

        # now notify all endpoints
        endpoints = notification_setting.get('endpoints', ['simple'])
        for endpoint_ref in endpoints:
            endpoint = self.endpoints.get(endpoint_ref, {})
            notification_type = endpoint.get('type', 'simple')
            notification_handler = self.notification_handlers[notification_type]

            log.debug(u"Notifying to endpoint {} about {}".format(endpoint_ref, pokemon['name']))
            notification_handler.notify_pokemon(endpoint, pokemon)

    def notify_gym(self, data, notification_setting):
        endpoints = notification_setting.get('endpoints', ['simple'])
        for endpoint_ref in endpoints:
            endpoint = self.endpoints.get(endpoint_ref, {})
            notification_type = endpoint.get('type', 'simple')
            notification_handler = self.notification_handlers[notification_type]

            notification_handler.notify_gym(endpoint, data)

    def notify_raid(self, pokemon, notification_setting):
        # find the handler and notify
        lat = pokemon['lat']
        lon = pokemon['lon']
        gym = self.gyms.get(pokemon['gym_id'])
        if gym is None:
            gym = {'name': '(Unknown)'}

        data = {
            'spawn': get_readable_time(pokemon['spawn']),
            'start': get_readable_time(pokemon['start']),
            'end': get_readable_time(pokemon['end']),
            'time_until_start': get_time_left(pokemon['start']),
            'time_until_end': get_time_left(pokemon['end']),
            'google_maps': get_google_maps(lat, lon),
            'static_google_maps': get_static_google_maps(lat, lon, self.google_key),
            'gamepress': get_gamepress(pokemon['id'])
        }
        pokemon.update(data)

        # add sublocality
        if self.fetch_sublocality and 'sublocality' not in pokemon:
            if not self.google_key:
                log.warn('You must provide a google api key in order to fetch sublocality')
                pokemon['sublocality'] = None
            else:
                pokemon['sublocality'] = get_sublocality(pokemon['lat'], pokemon['lon'], self.google_key)

        # now notify all endpoints
        endpoints = notification_setting.get('endpoints', ['simple'])
        for endpoint_ref in endpoints:
            endpoint = self.endpoints.get(endpoint_ref, {})
            notification_type = endpoint.get('type', 'simple')
            notification_handler = self.notification_handlers[notification_type]

            log.debug(u"Notifying to endpoint {} about raid on {}".format(endpoint_ref, pokemon['name']))
            notification_handler.notify_raid(endpoint, pokemon, gym)

    def handle_gym_details(self, message):
        parsed_gym = message['id']
        if parsed_gym not in self.gyms:
            # first scan of this gym
            self.gyms[parsed_gym] = {
                'name': message['name'],
                'lat': message['latitude'],
                'lon': message['longitude'],
                'team': message['team'],
                'pokemons': message['pokemon'],
                'trainers': [p['trainer_name'] for p in message['pokemon']]
            }

            # no further parsing. we only detect changes from here
            return

        gym = self.gyms[parsed_gym]
        trainers = [p['trainer_name'] for p in message['pokemon']]

        for notification_settings in self.notification_settings.itervalues():
            if not notification_settings.get('gym'):
                continue

            for tracked_trainer_name in self.trainers:

                if tracked_trainer_name in trainers:
                    # was he in the gym before?
                    trainer_existed = False
                    for trainer_name in gym.get('trainers', []):
                        if tracked_trainer_name == trainer_name:
                            # trainer is still in the gym
                            trainer_existed = True
                            break

                    if not trainer_existed:
                        # he wasn't in the gym before!
                        data = {
                            'trainer_name': tracked_trainer_name,
                            'name': gym['name'],
                            'lat': message['latitude'],
                            'lon': message['longitude'],
                            'team': message['team'],
                            'google_maps': get_google_maps(message['latitude'], message['longitude']),
                            'static_google_maps': get_static_google_maps(message['latitude'], message['longitude'],
                                                                         self.google_key)
                        }
                        log.info("%s joined gym: %s", tracked_trainer_name, gym['name'])
                        self.notify_gym(data, notification_settings)

        # finally update the gym for next time
        self.gyms[parsed_gym] = {
            'name': message['name'],
            'lat': message['latitude'],
            'lon': message['longitude'],
            'team': message['team'],
            'pokemons': message['pokemon'],
            'trainers': [p['trainer_name'] for p in message['pokemon']]
        }

    def handle_raid(self, message):
        if message['gym_id'] in self.processed_raids:
            log.debug('Raid Gym ID %s already processed.', message['gym_id'])
            return

        self.processed_raids[message['gym_id']] = datetime.datetime.utcfromtimestamp(message['end'])

        pokemon = {
            'id': message['pokemon_id'],
            'name': get_pokemon_name(message['pokemon_id']),
            'lat': message['latitude'],
            'lon': message['longitude'],
            'level': message['level'],
            'gym_id': message['gym_id'],
            'spawn': message['spawn'],
            'start': message['start'],
            'end': message['end'],
            'cp': message['cp'],
            'move_1': get_move_name(message['move_1']),
            'move_2': get_move_name(message['move_2'])
        }

        to_notify = set([])

        # Loop through all active includes and send notifications if appropriate
        for include_ref in self.includes:
            include = self.includes.get(include_ref)
            match = self.is_included_pokemon(pokemon, include)

            if match:
                notification_setting_refs = self.raid_includes_to_notifications.get(include_ref)

                if notification_setting_refs is not None:
                    for notification_setting_ref in notification_setting_refs:
                        to_notify.add(notification_setting_ref)
            else:
                log.debug('No match for %s in %s', pokemon['name'], include_ref)

        if to_notify:
            log.info('Notifying to %s', to_notify)
            for notification_setting_ref in to_notify:
                notification_setting = self.notification_settings.get(notification_setting_ref)
                self.notify_raid(pokemon, notification_setting)

    def enqueue(self, data):
        self.queue.put(data)

    def set_location(self, lat, lon):
        self.latitude = float(lat)
        self.longitude = float(lon)

        log.info("Location set to %s,%s" % (lat, lon))
