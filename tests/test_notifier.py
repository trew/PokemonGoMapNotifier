from notifier import Notifier, NotificationHandler
from notifier.manager import NotifierManager
import json
import unittest


class TestNotifier(unittest.TestCase):
    @staticmethod
    def _make_config(pokemons):
        return {
            "config": {
            },
            "includes": {
                "default_pokemon": {
                    "pokemons": [pokemons]
                }
            },
            "raid_includes": {
                "default_raid": {
                    "levels": [1, 2, 3, 4, 5]
                }
            },
            "notification_settings": {
                "Default": {
                    "includes": [
                        "default_pokemon"
                    ],
                    "raid_includes": [
                        "default_raid"
                    ]
                }
            }
        }

    @staticmethod
    def _make_geofence_config():
        return {
            "config": {
                "geofence_file": "tests/data/geofence/geofences.txt"
            },
            "includes": {
                "default_pokemon": {
                    "geofence": "Someplace",
                    "pokemons": [{'min_id': 1}]
                }
            },
            "notification_settings": {
                "Default": {
                    "includes": [
                        "default_pokemon"
                    ]
                }
            }
        }

    @staticmethod
    def _get_data(webhook):
        file_name = "tests/data/webhooks/" + webhook + ".json"

        with file(file_name, 'r') as fp:
            return json.load(fp)

    def setUp(self):
        config = self._make_config({"min_id": 0, "max_id": 999})
        self.notifiermanager = NotifierManager(config)
        self.config = self.notifiermanager.config
        self.notifier = self.notifiermanager.notifier
        self.notifierhandler = self.notifiermanager.handler
        self.notificationhandler = TestNotificationHandler()
        self.notifier.set_notification_handler("simple", self.notificationhandler)

    def test_pokemon_without_encounter(self):
        data = self._get_data("pokemon-without-encounter")

        def test(settings, pokemon):
            self.assertFalse('cp' in pokemon)
            self.assertFalse('form' in pokemon)
            self.assertFalse('attack' in pokemon)
            self.assertFalse('defense' in pokemon)
            self.assertFalse('stamina' in pokemon)
            self.assertFalse('move_1' in pokemon)
            self.assertFalse('move_2' in pokemon)
            self.assertFalse('level' in pokemon)
            self.assertFalse('iv' in pokemon)

        self.notificationhandler.on_pokemon = test
        self.notifierhandler.handle_pokemon(data['message'])

        self.assertTrue(self.notificationhandler.notify_pokemon_called)

    def test_pokemon_encounter(self):
        data = self._get_data("pokemon-with-encounter")

        def test(settings, pokemon):
            self.assertEqual(pokemon['cp'], 459)
            self.assertEqual(pokemon['level'], 19)
            self.assertEqual(pokemon['attack'], 8)
            self.assertEqual(pokemon['defense'], 10)
            self.assertEqual(pokemon['stamina'], 2)
            self.assertEqual(pokemon['move_1'], u'Quick Attack')
            self.assertEqual(pokemon['move_2'], u'Swift')
            self.assertAlmostEqual(pokemon['iv'], 44.44, places=2)
            self.assertFalse('form' in pokemon)

        self.notificationhandler.on_pokemon = test
        self.notifierhandler.handle_pokemon(data['message'])

        self.assertTrue(self.notificationhandler.notify_pokemon_called)

    def test_unown_encounter(self):
        data = self._get_data("unown-with-encounter")

        def test(settings, pokemon):
            self.assertEqual(pokemon['cp'], 459)
            self.assertEqual(pokemon['level'], 19)
            self.assertEqual(pokemon['form'], 'B')

        self.notificationhandler.on_pokemon = test
        self.notifierhandler.handle_pokemon(data['message'])

        self.assertTrue(self.notificationhandler.notify_pokemon_called)

    def test_raids(self):
        data = self._get_data("raid")

        def test(endpoint, raid):
            self.assertFalse(raid['egg'])

        self.notificationhandler.on_raid = test
        self.notifierhandler.handle_raid(data['message'])

        self.assertTrue(self.notificationhandler.notify_raid_called)

    def test_egg(self):
        data = self._get_data("egg")

        def test(endpoint, raid):
            self.assertTrue(raid['egg'])
            self.assertFalse('move_1' in raid)
            self.assertFalse('move_2' in raid)
            self.assertFalse('id' in raid)
            self.assertFalse('cp' in raid)

        self.notificationhandler.on_egg = test
        self.notifierhandler.handle_raid(data['message'])

        self.assertTrue(self.notificationhandler.notify_egg_called)

    def test_raid_and_then_egg(self):
        egg_data = self._get_data("egg")['message']
        raid_data = self._get_data("raid")['message']

        self.assertEqual(egg_data['start'], raid_data['start'])
        self.assertEqual(egg_data['gym_id'], raid_data['gym_id'])

        def test_egg(endpoint, raid):
            self.assertIsNotNone(raid)

        self.notificationhandler.on_egg = test_egg
        self.notifierhandler.handle_raid(egg_data)
        self.assertTrue(self.notificationhandler.notify_egg_called)
        self.assertFalse(self.notificationhandler.notify_raid_called)

        def test_raid(endpoint, raid):
            self.assertIsNotNone(raid)

        self.notificationhandler.on_raid = test_raid
        self.notifierhandler.handle_raid(raid_data)
        self.assertTrue(self.notificationhandler.notify_raid_called)

    def setup_geofence(self):
        config = self._make_geofence_config()
        self.notifiermanager = NotifierManager(config)
        self.config = self.notifiermanager.config
        self.notifier = self.notifiermanager.notifier
        self.notifierhandler = self.notifiermanager.handler
        self.notificationhandler = TestNotificationHandler()
        self.notifier.set_notification_handler("simple", self.notificationhandler)

    def test_inside_geofence(self):
        self.setup_geofence()

        message = self._get_data("pokemon-inside-geofence")['message']

        def test_geofence(endpoint, pokemon):
            self.assertIsNotNone(pokemon)

        self.notificationhandler.on_pokemon = test_geofence
        self.notifierhandler.handle_pokemon(message)

        self.assertTrue(self.notificationhandler.notify_pokemon_called)

    def test_outside_geofence(self):
        self.setup_geofence()

        message = self._get_data("pokemon-outside-geofence")['message']

        def test_geofence(endpoint, pokemon):
            self.assertIsNotNone(pokemon)

        self.notificationhandler.on_pokemon = test_geofence
        self.notifierhandler.handle_pokemon(message)

        self.assertFalse(self.notificationhandler.notify_pokemon_called)

    def test_way_outside_geofence(self):
        self.setup_geofence()

        message = self._get_data("pokemon-outside-geofence")['message']
        message['latitude'] = 150
        message['longitude'] = 150

        def test_geofence(endpoint, pokemon):
            self.assertIsNotNone(pokemon)

        self.notificationhandler.on_pokemon = test_geofence
        self.notifierhandler.handle_pokemon(message)

        self.assertFalse(self.notificationhandler.notify_pokemon_called)


class TestNotificationHandler(NotificationHandler):
    notify_gym_called = False
    notify_raid_called = False
    notify_egg_called = False
    notify_pokemon_called = False

    def on_gym(self, endpoint, gym):
        raise NotImplementedError("abstract method")

    def on_raid(self, endpoint, raid):
        raise NotImplementedError("abstract method")

    def on_egg(self, endpoint, egg):
        raise NotImplementedError("abstract method")

    def on_pokemon(self, settings, pokemon):
        raise NotImplementedError("abstract method")

    def notify_gym(self, endpoint, gym):
        self.notify_gym_called = True
        self.on_gym(endpoint, gym)

    def notify_raid(self, endpoint, raid):
        self.notify_raid_called = True
        self.on_raid(endpoint, raid)

    def notify_egg(self, endpoint, egg):
        self.notify_egg_called = True
        self.on_egg(endpoint, egg)

    def notify_pokemon(self, endpoint, pokemon):
        self.notify_pokemon_called = True
        self.on_pokemon(endpoint, pokemon)
