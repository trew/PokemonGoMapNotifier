from .. import NotificationHandler
import logging
import requests
import json

log = logging.getLogger(__name__)


class Discord(NotificationHandler):
    def notify_pokemon(self, settings, pokemon):
        url = settings.get('url')
        if not url:
            log.error("No url available to notify to")
            return

        data = self.create_embedded(pokemon)

        for i in range(0, 5):
            log.debug('Notifying Discord: %s' % data)
            if self.send(url, data):
                log.info('Discord notified: %s' % data)
                break

    @staticmethod
    def create_embedded(pokemon):
        description = u""
        if 'attack' in pokemon and 'defense' in pokemon and 'stamina' in pokemon:
            description += u"IV: **%s/%s/%s**\n" % (pokemon['attack'], pokemon['defense'], pokemon['stamina'])
        if 'move_1' in pokemon and 'move_2' in pokemon:
            description += u"Moves: **%s - %s**\n" % (pokemon['move_1'], pokemon['move_2'])
        description += u"[About %s](%s)" % (pokemon['name'], pokemon['gamepress'])

        thumbnail = u'https://raw.githubusercontent.com/kvangent/PokeAlarm/master/icons/{}.png'.format(
            pokemon['id'])
        return {
            'content': Discord.create_title(pokemon),
            'embeds': [{
                'title': u"Open Google Maps",
                'url': pokemon['google_maps'],
                'description': description,
                'thumbnail': {'url': thumbnail},
                'image': {'url': pokemon['static_google_maps']}
            }]
        }

    @staticmethod
    def create_title(pokemon):
        perfect_ivs = pokemon.get('iv') == 100
        anti_perfect_ivs = pokemon.get('iv') == 0

        if perfect_ivs:
            title = u"Perfect "
        elif anti_perfect_ivs:
            title = u"Shittiest possible "
        else:
            title = u""

        include_ivs = 'iv' in pokemon and not perfect_ivs and not anti_perfect_ivs

        title += u"**{}**".format(pokemon['name'])
        if include_ivs:
            title += u" (**{}%**)".format(int(round(pokemon['iv'])))

        if pokemon.get('sublocality'):
            title += u" in **{}** until **{}**".format(pokemon['sublocality'], pokemon['time'])
        else:
            title += u" found until **{}**".format(pokemon['time'])

        title += u" ({} left)!".format(pokemon['time_left'])
        return title

    @staticmethod
    def create_simple(pokemon):

        body = Discord.create_title(pokemon)

        if 'iv' in pokemon and 'move_1' in pokemon and 'move_2' in pokemon:
            body += u"\nIV: {}/{}/{} with **{} - {}**.".format(pokemon['attack'],
                                                               pokemon['defense'],
                                                               pokemon['stamina'],
                                                               pokemon['move_1'],
                                                               pokemon['move_2'])

        body += u"\nMaps: {}\nGP: {} Preview: {}".format(pokemon['google_maps'], pokemon['gamepress'],
                                                         pokemon['static_google_maps'])

        return {
            'content': body
        }

    @staticmethod
    def send(url, data):
        try:
            headers = {'Content-Type': 'application/json'}

            session = requests.Session()
            session.headers.update(headers)

            response = session.post(url, json=data, timeout=10)
        except requests.exceptions.ReadTimeout:
            log.warn('Response timed out on discord webhook %s', url)
            return False
        except requests.exceptions.RequestException:
            log.exception('Exception posting to discord webhook %s', url)
            return False

        if response.status_code != 200 and response.status_code != 204:
            log.error("Error: {} {}".format(response.status_code, response.reason))
            return False

        return True
