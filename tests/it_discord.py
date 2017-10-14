from notifier import Notifier, NotificationHandler
from notifier.manager import NotifierManager
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
            "raid_includes": {
                "default": {
                    "levels": [1, 2, 3, 4, 5]
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
                    "raid_includes": [
                        "default"
                    ]
                }
            }
        }

    @staticmethod
    def _get_data(webhook):
        filename = "tests/data/webhooks/" + webhook + ".json"

        with file(filename, 'r') as fp:
            return json.load(fp)

    def setUp(self):
        config = self._make_config({"min_id": 0, "max_id": 999})
        self.notifiermanager = NotifierManager(config)
        self.config = self.notifiermanager.config
        self.notifier = self.notifiermanager.notifier
        self.notifierhandler = self.notifiermanager.handler

    def test_pokemon_without_encounter(self):
        data = self._get_data("pokemon-without-encounter")
        self.notifierhandler.handle_pokemon(data['message'])

    def test_pokemon_encounter(self):
        data = self._get_data("pokemon-with-encounter")
        self.notifierhandler.handle_pokemon(data['message'])

    def test_unown_encounter(self):
        data = self._get_data("unown-with-encounter")
        self.notifierhandler.handle_pokemon(data['message'])

    def test_raids(self):
        data = self._get_data("raid")
        self.notifierhandler.handle_raid(data['message'])

    def test_egg(self):
        data = self._get_data("egg")
        self.notifierhandler.handle_raid(data['message'])

    def test_raid_and_then_egg(self):
        egg_data = self._get_data("egg")['message']
        raid_data = self._get_data("raid")['message']

        self.assertEqual(egg_data['start'], raid_data['start'])
        self.assertEqual(egg_data['gym_id'], raid_data['gym_id'])

        self.notifierhandler.handle_raid(egg_data)
        self.notifierhandler.handle_raid(raid_data)
