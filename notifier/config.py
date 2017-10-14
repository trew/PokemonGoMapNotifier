import logging
import commentjson as json


log = logging.getLogger(__name__)


class Config:
    def __init__(self, config_file):
        self.notification_handlers = {}
        self.pokemon_includes_to_notifications = {}
        self.raid_includes_to_notifications = {}
        self.google_key = None
        self.fetch_sublocality = False
        self.shorten_urls = False
        self.endpoints = {}
        self.trainers = []
        self.notification_settings = {}
        self.pokemon_includes = {}
        self.raid_includes = {}

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
        self.google_key = config.get('google_key', self.google_key)
        self.fetch_sublocality = config.get('fetch_sublocality', self.fetch_sublocality)
        self.shorten_urls = config.get('shorten_urls', self.shorten_urls)

        self.endpoints = parsed.get('endpoints', self.endpoints)
        self.trainers = parsed.get('trainers', self.trainers)

        from .simple import Simple
        self.notification_handlers['simple'] = Simple()

        for endpoint in self.endpoints:
            endpoint_type = self.endpoints[endpoint].get('type')
            if endpoint_type == 'discord' and 'discord' not in self.notification_handlers:
                log.info('Adding Discord to available notification handlers')
                from .discord import Discord
                self.notification_handlers['discord'] = Discord()

        self.pokemon_includes = parsed.get('includes', {})
        self.raid_includes = parsed.get('raid_includes', {})

        # filter out disabled notifiers
        parsed_notification_settings = parsed.get('notification_settings', {})
        self.notification_settings = {k: v for k, v in parsed_notification_settings.items() if v.get('enabled', True)}

        self.parse_pokemon_includes()
        self.parse_raid_includes()

        active_pokemon_includes = set()
        active_raid_includes = set()

        # loop through all notification settings
        for notification_setting in self.notification_settings:

            # get all include references for this notification setting
            for pokemon_include in self.notification_settings[notification_setting].get('includes', []):
                if pokemon_include not in self.pokemon_includes_to_notifications:
                    self.pokemon_includes_to_notifications[pokemon_include] = []

                # mark this include as active and create the link between includes and notifications
                active_pokemon_includes.add(pokemon_include)
                self.pokemon_includes_to_notifications[pokemon_include].append(notification_setting)

            # get all raid references for this notification setting
            for raid_include in self.notification_settings[notification_setting].get('raid_includes', []):
                if raid_include not in self.raid_includes_to_notifications:
                    self.raid_includes_to_notifications[raid_include] = []

                # mark this include as active and create the link between includes and notifications
                active_raid_includes.add(raid_include)
                self.raid_includes_to_notifications[raid_include].append(notification_setting)

        # remove includes that's not used by any notifications
        # also warn about it
        self.pokemon_includes = {k: v for k, v in self.pokemon_includes.items() if k in active_pokemon_includes}
        self.raid_includes = {k: v for k, v in self.raid_includes.items() if k in active_raid_includes}

        if not self.pokemon_includes and not self.raid_includes:
            raise RuntimeError('No includes configured')

        # remove includes refs, because they are not needed. simplifies debugging
        for notification_setting in self.notification_settings:
            # these references are covered by another dict, namely self.includes_to_notifications
            self.notification_settings[notification_setting].pop('includes', None)

            # if it's still here, it's enabled
            self.notification_settings[notification_setting].pop('enabled', None)

        # log some debug info
        for pokemon_include,notification_setting_refs in self.pokemon_includes_to_notifications.iteritems():
            log.debug('Notifying %s to %s', pokemon_include, notification_setting_refs)

        log.info('Initialized')

    def parse_pokemon_includes(self):
        self.resolve_pokemon_configurations()
        self.resolve_pokemon_refs()

        # bring the 'pokemons' entry to root level
        for include in self.pokemon_includes:
            self.pokemon_includes[include] = self.pokemon_includes[include]['pokemons']

    def parse_raid_includes(self):
        self.resolve_raid_configurations()
        #self.resolve_pokemon_refs()

    def resolve_pokemon_refs(self):
        for include in self.pokemon_includes:
            include = self.pokemon_includes[include]
            if 'pokemons' not in include:
                include['pokemons'] = []

            for ref in include.get('pokemons_refs', []):
                self.add_pokemons_from_ref(ref, include)

            include.pop('pokemons_refs', None)
            self.resolve_pokemon_configurations()

    def add_pokemons_from_ref(self, ref, include):
        resolved_ref = self.pokemon_includes.get(ref)

        if 'pokemons' in resolved_ref:
            for pokemon in resolved_ref['pokemons']:
                include['pokemons'].append(pokemon.copy())

        if 'pokemons_refs' in resolved_ref:
            for r in resolved_ref['pokemons_refs']:
                self.add_pokemons_from_ref(r, include)

    def resolve_raid_configurations(self):
        for include in self.raid_includes:
            include = self.raid_includes[include]

            for raid_pokemon in include.get('pokemons', []):
                self.add_if_missing('min_level', include, raid_pokemon)
                self.add_if_missing('max_level', include, raid_pokemon)
                self.add_if_missing('min_cp', include, raid_pokemon)
                self.add_if_missing('max_cp', include, raid_pokemon)
                self.add_if_missing('moves', include, raid_pokemon)
                self.add_if_missing('name', include, raid_pokemon)

    def resolve_pokemon_configurations(self):
        for include in self.pokemon_includes:
            include = self.pokemon_includes[include]

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

    @staticmethod
    def add_if_missing(key, source, target):
        if key in source and key not in target:
            target[key] = source[key]
