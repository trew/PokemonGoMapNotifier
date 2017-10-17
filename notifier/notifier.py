from .utils import *
import logging

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config):
        self.config = config

    def set_notification_handler(self, name, handler):
        self.config.notification_handlers[name] = handler

    def notify_pokemon(self, pokemon, message, notification_setting):
        # find the handler and notify
        lat = message['latitude']
        lon = message['longitude']
        data = {
            'encounter_id': message['encounter_id'],
            'time': get_readable_time(message['disappear_time']),
            'time_left': get_time_left(message['disappear_time']),
            'google_maps': get_google_maps(lat, lon),
            'static_google_maps': get_static_google_maps(lat, lon, self.config.google_key),
            'gamepress': get_gamepress(message['pokemon_id'])
        }
        pokemon.update(data)

        # add sublocality
        if self.config.fetch_sublocality and 'sublocality' not in pokemon:
            if not self.config.google_key:
                log.warn('You must provide a google api key in order to fetch sublocality')
                pokemon['sublocality'] = None
            else:
                pokemon['sublocality'] = get_sublocality(pokemon['lat'], pokemon['lon'], self.config.google_key)

        # now notify all endpoints
        endpoints = notification_setting.get('endpoints', ['simple'])
        for endpoint_ref in endpoints:
            endpoint = self.config.endpoints.get(endpoint_ref, {})
            notification_type = endpoint.get('type', 'simple')
            notification_handler = self.config.notification_handlers[notification_type]

            log.debug(u"Notifying to endpoint {} about {}".format(endpoint_ref, pokemon['name']))
            notification_handler.notify_pokemon(endpoint, pokemon)

    def notify_gym(self, data, notification_setting):
        endpoints = notification_setting.get('endpoints', ['simple'])
        for endpoint_ref in endpoints:
            endpoint = self.config.endpoints.get(endpoint_ref, {})
            notification_type = endpoint.get('type', 'simple')
            notification_handler = self.config.notification_handlers[notification_type]

            notification_handler.notify_gym(endpoint, data)

    def notify_raid_or_egg(self, raid_in, notification_setting):
        # find the handler and notify
        lat = raid_in['lat']
        lon = raid_in['lon']

        raid = {
            'spawn': get_readable_time(raid_in['spawn']),
            'start': get_readable_time(raid_in['start']),
            'end': get_readable_time(raid_in['end']),
            'time_until_start': get_time_left(raid_in['start']),
            'time_until_end': get_time_left(raid_in['end']),
            'google_maps': get_google_maps(lat, lon),
            'static_google_maps': get_static_google_maps(lat, lon, self.config.google_key),
        }

        if raid_in.get('id'):
            raid['gamepress'] = get_gamepress(raid_in['id'])

        raid.update(raid_in)

        if raid['gym'] is None:
            raid['gym'] = {'name': '(Unknown)'}

        # add sublocality
        if self.config.fetch_sublocality and 'sublocality' not in raid:
            if not self.config.google_key:
                log.warn('You must provide a google api key in order to fetch sublocality')
                raid['sublocality'] = None
            else:
                raid['sublocality'] = get_sublocality(raid['lat'], raid['lon'], self.config.google_key)

        # now notify all endpoints
        endpoints = notification_setting.get('endpoints', ['simple'])
        for endpoint_ref in endpoints:
            endpoint = self.config.endpoints.get(endpoint_ref, {})
            notification_type = endpoint.get('type', 'simple')
            notification_handler = self.config.notification_handlers[notification_type]

            log.debug(
                u"Notifying to endpoint {} about {} on {}".format(endpoint_ref, "egg" if raid["egg"] else "raid",
                                                                  raid['name']))
            if raid['egg']:
                notification_handler.notify_egg(endpoint, raid)
            else:
                notification_handler.notify_raid(endpoint, raid)
