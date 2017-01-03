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

        body = self.create_body(pokemon)

        headers = {'Content-Type': 'application/json'}

        session = requests.Session()
        session.headers.update(headers)
        body = {
            'content': body
        }

        body = json.dumps(body)
        log.debug('Notifying Discord: %s' % body)
        for i in range(0, 5):
            if self.send(session, url, body):
                log.info('Discord notified: %s' % body)
                break

    @staticmethod
    def create_body(pokemon):
        perfect_ivs = pokemon.get('iv', -1) == 45
        anti_perfect_ivs = pokemon.get('iv') == 0

        if perfect_ivs:
            body = u"Perfect "
        elif anti_perfect_ivs:
            body = u"Shittiest possible "
        else:
            body = u""

        include_ivs = 'iv' in pokemon and not perfect_ivs and not anti_perfect_ivs

        body += u"**{}**".format(pokemon['name'])
        if include_ivs:
            body += u" (**{}%**)".format(int(round(pokemon['iv'])))

        if pokemon.get('sublocality'):
            body += u" in **{}** until **{}**".format(pokemon['sublocality'], pokemon['time'])
        else:
            body += u" found until **{}**".format(pokemon['time'])

        body += u" ({} left)!".format(pokemon['time_left'])

        if 'iv' in pokemon and 'move_1' in pokemon and 'move_2' in pokemon:
            body += u"\nIV: {}/{}/{} with **{} - {}**.".format(pokemon['attack'],
                                                               pokemon['defense'],
                                                               pokemon['stamina'],
                                                               pokemon['move_1'],
                                                               pokemon['move_2'])

        body += u"\nMaps: {}\nGP: {} Preview: {}".format(pokemon['google_maps'], pokemon['gamepress'],
                                                         pokemon['static_google_maps'])

        return body

    @staticmethod
    def send(session, url, body):
        try:
            response = session.post(url, data=body)
        except Exception as e:
            print "Exception {}".format(e)
            return False
        else:
            if response.status_code != 200 and response.status_code != 204:
                log.error("Error: {} {}".format(response.status_code, response.reason))
                return False

            return True
