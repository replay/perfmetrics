
try:
    import unittest2 as unittest
except ImportError:
    import unittest


class Test_statsd_config_functions(unittest.TestCase):

    def setUp(self):
        from perfmetrics import set_statsd_client
        set_statsd_client(None)

    tearDown = setUp

    def test_unconfigured(self):
        from perfmetrics import statsd_client
        self.assertIsNone(statsd_client())

    def test_configured_with_uri(self):
        from perfmetrics import set_statsd_client
        set_statsd_client('statsd://localhost:8125')
        from perfmetrics import StatsdClient
        from perfmetrics import statsd_client
        self.assertIsInstance(statsd_client(), StatsdClient)

    def test_configured_with_other_client(self):
        other_client = object()
        from perfmetrics import set_statsd_client
        set_statsd_client(other_client)
        from perfmetrics import statsd_client
        self.assertIs(statsd_client(), other_client)


class Test_statsd_client_from_uri(unittest.TestCase):

    def _call(self, uri):
        from perfmetrics import statsd_client_from_uri
        return statsd_client_from_uri(uri)

    def test_local_uri(self):
        client = self._call('statsd://localhost:8129')
        self.assertIsNotNone(client.udp_sock)

    def test_unsupported_uri(self):
        with self.assertRaises(ValueError):
            self._call('http://localhost:8125')

    def test_with_custom_gauge_suffix(self):
        client = self._call('statsd://localhost:8129?gauge_suffix=.spamalot')
        self.assertEqual(client.gauge_suffix, '.spamalot')


class TestMetric(unittest.TestCase):

    @property
    def _class(self):
        from perfmetrics import Metric
        return Metric

    @property
    def statsd_client_stack(self):
        from perfmetrics import statsd_client_stack
        return statsd_client_stack

    def setUp(self):
        self.statsd_client_stack.clear()

    tearDown = setUp

    def _add_client(self):
        self.changes = changes = []
        self.timing = timing = []
        self.sentbufs = sentbufs = []

        class DummyStatsdClient:
            def change(self, stat, delta, sample_rate, buf=None):
                changes.append((stat, delta, sample_rate, buf))

            def timing(self, stat, ms, sample_rate, buf=None):
                timing.append((stat, ms, sample_rate, buf))

            def sendbuf(self, buf):
                sentbufs.append(buf)

        self.statsd_client_stack.push(DummyStatsdClient())

    def test_ctor_with_defaults(self):
        obj = self._class()
        self.assertIsNone(obj.stat)
        self.assertEqual(obj.sample_rate, 1)
        self.assertTrue(obj.count)
        self.assertTrue(obj.timing)

    def test_ctor_with_options(self):
        obj = self._class('spam.n.eggs', 0.1, count=False, timing=False)
        self.assertEqual(obj.stat, 'spam.n.eggs')
        self.assertEqual(obj.sample_rate, 0.1)
        self.assertFalse(obj.count)
        self.assertFalse(obj.timing)

    def test_decorate_function(self):
        args = []
        metric = self._class()

        @metric
        def spam(x, y=2):
            args.append((x, y))

        self.assertEqual(spam.__module__, __name__)
        self.assertEqual(spam.__name__, 'spam')

        # Call with no statsd client configured.
        spam(4, 5)
        self.assertEqual(args, [(4, 5)])
        del args[:]

        # Call with a statsd client configured.
        self._add_client()
        spam(6, 1)
        self.assertEqual(args, [(6, 1)])
        self.assertEqual(self.changes, [(__name__ + '.spam', 1, 1, [])])
        self.assertEqual(len(self.timing), 1)
        stat, ms, sample_rate, _buf = self.timing[0]
        self.assertEqual(stat, __name__ + '.spam')
        self.assertGreaterEqual(ms, 0)
        self.assertLess(ms, 10000)
        self.assertEqual(sample_rate, 1)

    def test_decorate_method(self):
        args = []
        metricmethod = self._class(method=True)

        class Spam:
            @metricmethod
            def f(self, x, y=2):
                args.append((x, y))

        self.assertEqual(Spam.f.__module__, __name__)
        self.assertEqual(Spam.f.__name__, 'f')
        self.assertEqual(Spam.f.im_class, Spam)

        # Call with no statsd client configured.
        Spam().f(4, 5)
        self.assertEqual(args, [(4, 5)])
        del args[:]

        # Call with a statsd client configured.
        self._add_client()
        Spam().f(6, 1)
        self.assertEqual(args, [(6, 1)])
        self.assertEqual(self.changes, [(__name__ + '.Spam.f', 1, 1, [])])
        self.assertEqual(len(self.timing), 1)
        stat, ms, sample_rate, _buf = self.timing[0]
        self.assertEqual(stat, 'perfmetrics.tests.test_perfmetrics.Spam.f')
        self.assertGreaterEqual(ms, 0)
        self.assertLess(ms, 10000)
        self.assertEqual(sample_rate, 1)

    def test_decorate_with_options(self):
        args = []
        Metric = self._class

        @Metric('spammy', sample_rate=0.1, timing=False)
        def spam(x, y=2):
            args.append((x, y))

        self.assertEqual(spam.__module__, __name__)
        self.assertEqual(spam.__name__, 'spam')

        # Call with no statsd client configured.
        spam(4, 5)
        self.assertEqual(args, [(4, 5)])
        del args[:]

        # Call with a statsd client configured.
        self._add_client()
        spam(6, 1)
        self.assertEqual(args, [(6, 1)])
        self.assertEqual(self.changes, [('spammy', 1, 0.1, None)])
        self.assertEqual(len(self.timing), 0)