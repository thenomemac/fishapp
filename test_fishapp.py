import logging
import unittest

import fishapp


class FishappTestCase(unittest.TestCase):

    def setUp(self):
        fishapp.app.testing = True
        self.app = fishapp.app.test_client()
        log.info('Setting up...')

    def tearDown(self):
        log.info('Tearing down...')

    def test_index(self):
        rv = self.app.get('/')
        log.info(rv)
        html_str = rv.data.decode('utf-8').lower()
        assert 'whatismyfish.net' in html_str, 'Bad data'


if __name__ == '__main__':
    logging.basicConfig(level=logging.debug)
    log = logging.getLogger(__file__)
    log.info('Shall we begin...')
    unittest.main()
