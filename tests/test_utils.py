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

    def test_get_level_from_cpm(self):
        # level 29 as reported from the api
        level = utils.get_level_from_cpm(0.719399094581604)
        self.assertEqual(level, 29)

        for i in range(1, 30):
            cpm = utils.get_cpm_for_level(i)
            level = utils.get_level_from_cpm(cpm)
            self.assertEqual(level, i)

    def test_point_in_poly(self):
        poly = [(40,30), (30, 20), (40, 10), (50,20)]
        mid_point = (40, 20)
        outside = (35, 25)

        self.assertTrue(utils.point_in_poly(mid_point[0], mid_point[1], poly))
        self.assertFalse(utils.point_in_poly(outside[0], outside[1], poly))

        poly = [(47.69030553853416,-122.3214340209961),
            (47.64128858814697,-122.41310119628906),
            (47.572077942751605,-122.31868743896484),
                (47.62393666282315,-122.22599029541016)]

        inside = (47.64545219291908,-122.38632202148438)
        outside = (47.59292021272622,-122.26753234863281)

        self.assertTrue(utils.point_in_poly(inside[0], inside[1], poly))
        self.assertFalse(utils.point_in_poly(outside[0], outside[1], poly))