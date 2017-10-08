from notifier import Notifier, NotificationHandler
import json
import unittest


class TestNotifier(unittest.TestCase):
    @staticmethod
    def _make_config(pokemons):
        return {
            "config": {
            },
            "includes": {
                "default": {
                    "pokemons": [pokemons]
                }
            },
            "notification_settings": {
                "Default": {
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
    def _get_data(pokemon=False, encounter=False, gym_details=False, raid=False):
        file_name = None
        if pokemon:
            if encounter:
                return None  # todo fix file with encounter data
            else:
                file_name = "tests/data/pokemon-without-encounter.json"
        elif gym_details:
            file_name = "tests/data/gym-details.json"
        elif raid:
            file_name = "tests/data/raid.json"

        with file(file_name, 'r') as fp:
            return json.load(fp)

    def test_notifier(self):
        data = self._get_data(pokemon=True, encounter=False)
        config = self._make_config({"min_id": 0, "max_id": 151})
        notifier = Notifier(config)
        handler = TestNotificationHandler()
        handler.on_pokemon = lambda settings, pokemon: self.assertIsNotNone(pokemon)
        notifier.set_notification_handler("simple", handler)
        notifier.handle_pokemon(data['message'])

        self.assertTrue(handler.notify_pokemon_called)

    def test_raids(self):
        data = self._get_data(raid=True)
        config = self._make_config({"min_id": 0, "max_id": 9990})
        notifier = Notifier(config)
        handler = TestNotificationHandler()
        handler.on_raid = lambda endpoint, raid, gym: self.assertIsNotNone(raid)
        notifier.set_notification_handler("simple", handler)
        notifier.handle_raid(data['message'])

        self.assertTrue(handler.notify_raid_called)


class TestNotificationHandler(NotificationHandler):
    notify_gym_called = False
    notify_raid_called = False
    notify_pokemon_called = False

    def on_gym(self):
        raise NotImplementedError("abstract method")

    def on_raid(self):
        raise NotImplementedError("abstract method")

    def on_pokemon(self):
        raise NotImplementedError("abstract method")

    def notify_gym(self, endpoint, gym):
        self.notify_gym_called = True
        self.on_gym(endpoint, gym)

    def notify_raid(self, endpoint, raid, gym):
        self.notify_raid_called = True
        self.on_raid(endpoint, raid, gym)

    def notify_pokemon(self, settings, pokemon):
        self.notify_pokemon_called = True
        self.on_pokemon(settings, pokemon)
