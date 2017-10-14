from notifier import Notifier, NotificationHandler
import os
import json
import unittest


class TestNotifier(unittest.TestCase):
    @staticmethod
    def _make_config(pokemons):
        channel_url = os.environ.get('DISCORD_URL')
        if channel_url is None:
            raise RuntimeError("No channel url")
        return {
            "config": {
            },
            "endpoints": {
                "discord": {
                    "type": "discord",
                    "url": channel_url
                }
            },
            "includes": {
                "default": {
                    "pokemons": [pokemons]
                }
            },
            "notification_settings": {
                "Default": {
                    "endpoints": [
                        "discord"
                    ],
                    "includes": [
                        "default"
                    ],
                    "raids": [
                        "default"
                    ]
                }
            }
        }

    @staticmethod
    def _get_data(pokemon=False, encounter=False, gym_details=False, raid=False, egg=False, custom=None):
        file_name = None
        if pokemon:
            if encounter:
                file_name = "tests/data/pokemon-with-encounter.json"
            else:
                file_name = "tests/data/pokemon-without-encounter.json"
        elif gym_details:
            file_name = "tests/data/gym-details.json"
        elif raid:
            file_name = "tests/data/raid.json"
        elif egg:
            file_name = "tests/data/egg.json"
        elif custom is not None:
            file_name = "tests/data/" + custom

        with file(file_name, 'r') as fp:
            return json.load(fp)

    def test_pokemon_without_encounter(self):
        data = self._get_data(pokemon=True, encounter=False)
        config = self._make_config({"min_id": 0, "max_id": 151})
        notifier = Notifier(config)
        notifier.handle_pokemon(data['message'])

    def test_pokemon_encounter(self):
        data = self._get_data(pokemon=True, encounter=True)
        config = self._make_config({"min_id": 0, "max_id": 151})
        notifier = Notifier(config)
        notifier.handle_pokemon(data['message'])

    def test_unown_encounter(self):
        data = self._get_data(custom="unown-with-encounter.json")
        config = self._make_config({"min_id": 0, "max_id": 151})
        notifier = Notifier(config)
        notifier.handle_pokemon(data['message'])

    def test_raids(self):
        data = self._get_data(raid=True)
        config = self._make_config({"min_id": 0, "max_id": 999})
        notifier = Notifier(config)
        notifier.handle_raid(data['message'])

    def test_egg(self):
        data = self._get_data(egg=True)
        config = self._make_config({"min_id": 0, "max_id": 999})
        notifier = Notifier(config)
        notifier.handle_raid(data['message'])

    def test_raid_and_then_egg(self):
        egg_data = self._get_data(egg=True)['message']
        raid_data = self._get_data(raid=True)['message']

        self.assertEqual(egg_data['start'], raid_data['start'])
        self.assertEqual(egg_data['gym_id'], raid_data['gym_id'])

        config = self._make_config({"min_id": 0, "max_id": 999})
        notifier = Notifier(config)

        notifier.handle_raid(egg_data)
        notifier.handle_raid(raid_data)
