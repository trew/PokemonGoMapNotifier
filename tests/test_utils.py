from notifier import utils
import unittest


class TestUtils(unittest.TestCase):
    def test_get_stats(self):
        stats = utils.get_stats(1)
        self.assertEqual(stats.get('name'), 'Bulbasaur')

    def test_get_cp_for_level(self):
        # Bulbasaur at level 1 with 0,0,0 = 10
        cp = utils.get_cp_for_level(1, 1, 0, 0, 0)
        self.assertEqual(cp, 10)

        # Dragonite at level 39 with 15,15,15 == 3530
        cp = utils.get_cp_for_level(149, 39, 15, 15, 15)
        self.assertEqual(cp, 3530)

    def test_get_hp_for_level(self):
        # Dragonite at level 39 with 15,15,15 == 154
        hp = utils.get_hp_for_level(149, 39, 15)
        self.assertEqual(hp, 154)

        # Snorlax at level 12 with 15,14,14
        hp = utils.get_hp_for_level(143, 12, 14)
        self.assertEqual(hp, 154)
