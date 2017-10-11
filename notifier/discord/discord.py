from .. import NotificationHandler
from .. import utils
import logging
import requests

log = logging.getLogger(__name__)


class Discord(NotificationHandler):
    def notify_pokemon(self, endpoint, pokemon):
        url = endpoint.get('url')
        if not url:
            log.error("No url available to notify to")
            return

        data = self.create_embedded(pokemon)

        self.try_sending(url, data)

    def notify_gym(self, endpoint, gym):
        url = endpoint.get('url')
        if not url:
            log.error("No url available to notify to")
            return

        content = '**%s** joined a gym!' % gym.get('trainer_name')
        embed = {
            'title': u"Open Google Maps",
            'url': gym.get('google_maps'),
            'image': {'url': gym.get('static_google_maps')}
        }

        name = gym.get('name')
        team_name = utils.get_team_name(gym.get('team'))
        if team_name:
            embed['description'] = 'Gym Name: %s\nGym Team: %s' % (name, team_name)
            icon = 'https://raw.githubusercontent.com/kvangent/PokeAlarm/master/icons/gym_%s.png' % team_name.lower()
            embed['thumbnail'] = {'url': icon}
        else:
            embed['description'] = 'Gym Name: %s' % name

        data = {
            'content': content,
            'embeds': [embed]
        }

        self.try_sending(url, data)

    def notify_raid(self, endpoint, raid, gym):
        url = endpoint.get('url')
        if not url:
            log.error("No url available to notify to")
            return

        data = self.create_raid_embedded(raid, gym)

        self.try_sending(url, data)

    @staticmethod
    def create_raid_embedded(raid, gym):
        title = '%s raid at %s starting %s (%s left) until %s (%s left)!' % (raid.get('name'),
                                                                             gym.get('name'),
                                                                             raid.get('start'),
                                                                             raid.get('time_until_start'),
                                                                             raid.get('end'),
                                                                             raid.get('time_until_end'))
        description = u"Raid Level: **%s**\n" % raid['level']
        description += u"CP: **%s**\n" % raid['cp']
        description += u"Moves: **%s - %s**\n" % (raid['move_1'], raid['move_2'])
        description += u"[About %s](%s)" % (raid['name'], raid['gamepress'])

        thumbnail = u'https://raw.githubusercontent.com/kvangent/PokeAlarm/master/icons/{}.png'.format(raid['id'])
        return {
            'content': title,
            'embeds': [{
                'title': u"Open Google Maps",
                'url': raid['google_maps'],
                'description': description,
                'thumbnail': {'url': thumbnail},
                'image': {'url': raid['static_google_maps']}
            }]
        }

    @staticmethod
    def create_embedded(pokemon):
        description = u""
        if 'attack' in pokemon and 'defense' in pokemon and 'stamina' in pokemon:
            description += u"IV: **%s/%s/%s**\n" % (pokemon['attack'], pokemon['defense'], pokemon['stamina'])
        if 'move_1' in pokemon and 'move_2' in pokemon:
            description += u"Moves: **%s - %s**\n" % (pokemon['move_1'], pokemon['move_2'])
        if 'form' in pokemon:
            description += u"Form: **%s**\n" % pokemon['form']
        if 'cp' in pokemon and 'level' in pokemon:
            cp = pokemon.get('cp')
            level = pokemon.get('level')
            player_level = pokemon.get('player_level')
            if int(player_level) > 30:
                player_level = '30+'

            description += u"CP for level %s: **%s** (Level **%s**)\n" % (player_level, cp, level)

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

        if 'form' in pokemon:
            title += u"(**{}**)".format(pokemon['form'])

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

    def try_sending(self, url, data):
        for i in range(0, 5):
            log.debug('Notifying Discord: %s' % data)
            if self.send(url, data):
                log.info('Discord notified: %s' % data)
                return True

        log.error("Failed notification to %s: %s", url, data)
        return False

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
