import os
import json
from subprocess import CalledProcessError
import shutil
import tempfile
from mock import call, MagicMock, mock_open, patch, sentinel
from testtools import TestCase
import yaml

import six
import io

from charmhelpers.core import hookenv

if six.PY3:
    import pickle
else:
    import cPickle as pickle


CHARM_METADATA = b"""name: testmock
summary: test mock summary
description: test mock description
requires:
    testreqs:
        interface: mock
provides:
    testprov:
        interface: mock
peers:
    testpeer:
        interface: mock
"""


class ConfigTest(TestCase):
    def setUp(self):
        super(ConfigTest, self).setUp()

        self.charm_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.charm_dir))

        patcher = patch.object(hookenv, 'charm_dir', lambda: self.charm_dir)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_init(self):
        d = dict(foo='bar')
        c = hookenv.Config(d)

        self.assertEqual(c['foo'], 'bar')
        self.assertEqual(c._prev_dict, None)

    def test_load_previous(self):
        d = dict(foo='bar')
        c = hookenv.Config()

        with open(c.path, 'w') as f:
            json.dump(d, f)

        c.load_previous()
        self.assertEqual(c._prev_dict, d)

    def test_load_previous_alternate_path(self):
        d = dict(foo='bar')
        c = hookenv.Config()

        alt_path = os.path.join(self.charm_dir, '.alt-config')
        with open(alt_path, 'w') as f:
            json.dump(d, f)

        c.load_previous(path=alt_path)
        self.assertEqual(c._prev_dict, d)
        self.assertEqual(c.path, alt_path)

    def test_changed_without_prev_dict(self):
        d = dict(foo='bar')
        c = hookenv.Config(d)

        self.assertTrue(c.changed('foo'))

    def test_changed_with_prev_dict(self):
        c = hookenv.Config(dict(foo='bar', a='b'))
        c.save()
        c = hookenv.Config(dict(foo='baz', a='b'))

        self.assertTrue(c.changed('foo'))
        self.assertFalse(c.changed('a'))

    def test_previous_without_prev_dict(self):
        c = hookenv.Config()

        self.assertEqual(c.previous('foo'), None)

    def test_previous_with_prev_dict(self):
        c = hookenv.Config(dict(foo='bar'))
        c.save()
        c = hookenv.Config(dict(foo='baz', a='b'))

        self.assertEqual(c.previous('foo'), 'bar')
        self.assertEqual(c.previous('a'), None)

    def test_save_without_prev_dict(self):
        c = hookenv.Config(dict(foo='bar'))
        c.save()

        with open(c.path, 'r') as f:
            self.assertEqual(c, json.load(f))
            self.assertEqual(c, dict(foo='bar'))

    def test_save_with_prev_dict(self):
        c = hookenv.Config(dict(foo='bar'))
        c.save()
        c = hookenv.Config(dict(a='b'))
        c.save()

        with open(c.path, 'r') as f:
            self.assertEqual(c, json.load(f))
            self.assertEqual(c, dict(foo='bar', a='b'))

    def test_getitem(self):
        c = hookenv.Config(dict(foo='bar'))
        c.save()
        c = hookenv.Config(dict(baz='bam'))

        self.assertRaises(KeyError, lambda: c['missing'])
        self.assertEqual(c['foo'], 'bar')
        self.assertEqual(c['baz'], 'bam')

    def test_get(self):
        c = hookenv.Config(dict(foo='bar'))
        c.save()
        c = hookenv.Config(dict(baz='bam'))

        self.assertIsNone(c.get('missing'))
        self.assertIs(c.get('missing', sentinel.missing), sentinel.missing)
        self.assertEqual(c.get('foo'), 'bar')
        self.assertEqual(c.get('baz'), 'bam')

    def test_keys(self):
        c = hookenv.Config(dict(foo='bar'))
        c["baz"] = "bar"
        self.assertEqual(sorted([six.u("foo"), "baz"]), sorted(c.keys()))

    def test_in(self):
        # Test behavior of the in operator.

        # Items that exist in the dict exist. Items that don't don't.
        c = hookenv.Config(dict(foo='one'))
        self.assertTrue('foo' in c)
        self.assertTrue('bar' not in c)
        c.save()
        self.assertTrue('foo' in c)
        self.assertTrue('bar' not in c)

        # Adding items works as expected.
        c['foo'] = 'two'
        c['bar'] = 'two'
        self.assertTrue('foo' in c)
        self.assertTrue('bar' in c)
        c.save()
        self.assertTrue('foo' in c)
        self.assertTrue('bar' in c)

        # Removing items works as expected.
        del c['foo']
        self.assertTrue('foo' not in c)
        c.save()
        self.assertTrue('foo' not in c)


class SerializableTest(TestCase):
    def test_serializes_object_to_json(self):
        foo = {
            'bar': 'baz',
        }
        wrapped = hookenv.Serializable(foo)
        self.assertEqual(wrapped.json(), json.dumps(foo))

    def test_serializes_object_to_yaml(self):
        foo = {
            'bar': 'baz',
        }
        wrapped = hookenv.Serializable(foo)
        self.assertEqual(wrapped.yaml(), yaml.dump(foo))

    def test_gets_attribute_from_inner_object_as_dict(self):
        foo = {
            'bar': 'baz',
        }
        wrapped = hookenv.Serializable(foo)

        self.assertEqual(wrapped.bar, 'baz')

    def test_raises_error_from_inner_object_as_dict(self):
        foo = {
            'bar': 'baz',
        }
        wrapped = hookenv.Serializable(foo)

        self.assertRaises(AttributeError, getattr, wrapped, 'baz')

    def test_dict_methods_from_inner_object(self):
        foo = {
            'bar': 'baz',
        }
        wrapped = hookenv.Serializable(foo)
        for meth in ('keys', 'values', 'items'):
            self.assertEqual(sorted(list(getattr(wrapped, meth)())),
                             sorted(list(getattr(foo, meth)())))

        self.assertEqual(wrapped.get('bar'), foo.get('bar'))
        self.assertEqual(wrapped.get('baz', 42), foo.get('baz', 42))
        self.assertIn('bar', wrapped)

    def test_get_gets_from_inner_object(self):
        foo = {
            'bar': 'baz',
        }
        wrapped = hookenv.Serializable(foo)

        self.assertEqual(wrapped.get('foo'), None)
        self.assertEqual(wrapped.get('bar'), 'baz')
        self.assertEqual(wrapped.get('zoo', 'bla'), 'bla')

    def test_gets_inner_object(self):
        foo = {
            'bar': 'baz',
        }
        wrapped = hookenv.Serializable(foo)

        self.assertIs(wrapped.data, foo)

    def test_pickle(self):
        foo = {'bar': 'baz'}
        wrapped = hookenv.Serializable(foo)
        pickled = pickle.dumps(wrapped)
        unpickled = pickle.loads(pickled)

        self.assert_(isinstance(unpickled, hookenv.Serializable))
        self.assertEqual(unpickled, foo)

    def test_boolean(self):
        true_dict = {'foo': 'bar'}
        false_dict = {}

        self.assertIs(bool(hookenv.Serializable(true_dict)), True)
        self.assertIs(bool(hookenv.Serializable(false_dict)), False)

    def test_equality(self):
        foo = {'bar': 'baz'}
        bar = {'baz': 'bar'}
        wrapped_foo = hookenv.Serializable(foo)

        self.assertEqual(wrapped_foo, foo)
        self.assertEqual(wrapped_foo, wrapped_foo)
        self.assertNotEqual(wrapped_foo, bar)


class HelpersTest(TestCase):
    def setUp(self):
        super(HelpersTest, self).setUp()
        # Reset hookenv cache for each test
        hookenv.cache = {}

    @patch('subprocess.call')
    def test_logs_messages_to_juju_with_default_level(self, mock_call):
        hookenv.log('foo')

        mock_call.assert_called_with(['juju-log', 'foo'])

    @patch('subprocess.call')
    def test_logs_messages_object(self, mock_call):
        hookenv.log(object)
        mock_call.assert_called_with(['juju-log', repr(object)])

    @patch('subprocess.call')
    def test_logs_messages_with_alternative_levels(self, mock_call):
        alternative_levels = [
            hookenv.CRITICAL,
            hookenv.ERROR,
            hookenv.WARNING,
            hookenv.INFO,
        ]

        for level in alternative_levels:
            hookenv.log('foo', level)
            mock_call.assert_called_with(['juju-log', '-l', level, 'foo'])

    @patch('subprocess.check_output')
    def test_gets_charm_config_with_scope(self, check_output):
        config_data = 'bar'
        check_output.return_value = json.dumps(config_data).encode('UTF-8')

        result = hookenv.config(scope='baz')

        self.assertEqual(result, 'bar')
        check_output.assert_called_with(['config-get', 'baz', '--format=json'])

        # The result can be used like a string
        self.assertEqual(result[1], 'a')

        # ... because the result is actually a string
        self.assert_(isinstance(result, six.string_types))

    @patch('subprocess.check_output')
    def test_gets_missing_charm_config_with_scope(self, check_output):
        check_output.return_value = b''

        result = hookenv.config(scope='baz')

        self.assertEqual(result, None)
        check_output.assert_called_with(['config-get', 'baz', '--format=json'])

    @patch('charmhelpers.core.hookenv.charm_dir')
    @patch('subprocess.check_output')
    def test_gets_config_without_scope(self, check_output, charm_dir):
        check_output.return_value = json.dumps(dict(foo='bar')).encode('UTF-8')
        charm_dir.side_effect = tempfile.mkdtemp

        result = hookenv.config()

        self.assertIsInstance(result, hookenv.Config)
        self.assertEqual(result['foo'], 'bar')
        check_output.assert_called_with(['config-get', '--format=json'])

    @patch('charmhelpers.core.hookenv.os')
    def test_gets_the_local_unit(self, os_):
        os_.environ = {
            'JUJU_UNIT_NAME': 'foo',
        }

        self.assertEqual(hookenv.local_unit(), 'foo')

    @patch('charmhelpers.core.hookenv.unit_get')
    def test_gets_unit_public_ip(self, _unitget):
        _unitget.return_value = sentinel.public_ip
        self.assertEqual(sentinel.public_ip, hookenv.unit_public_ip())
        _unitget.assert_called_once_with('public-address')

    @patch('charmhelpers.core.hookenv.unit_get')
    def test_gets_unit_private_ip(self, _unitget):
        _unitget.return_value = sentinel.private_ip
        self.assertEqual(sentinel.private_ip, hookenv.unit_private_ip())
        _unitget.assert_called_once_with('private-address')

    @patch('charmhelpers.core.hookenv.os')
    def test_checks_that_is_running_in_relation_hook(self, os_):
        os_.environ = {
            'JUJU_RELATION': 'foo',
        }

        self.assertTrue(hookenv.in_relation_hook())

    @patch('charmhelpers.core.hookenv.os')
    def test_checks_that_is_not_running_in_relation_hook(self, os_):
        os_.environ = {
            'bar': 'foo',
        }

        self.assertFalse(hookenv.in_relation_hook())

    @patch('charmhelpers.core.hookenv.os')
    def test_gets_the_relation_type(self, os_):
        os_.environ = {
            'JUJU_RELATION': 'foo',
        }

        self.assertEqual(hookenv.relation_type(), 'foo')

    @patch('charmhelpers.core.hookenv.os')
    def test_relation_type_none_if_not_in_environment(self, os_):
        os_.environ = {}
        self.assertEqual(hookenv.relation_type(), None)

    @patch('subprocess.check_output')
    @patch('charmhelpers.core.hookenv.relation_type')
    def test_gets_relation_ids(self, relation_type, check_output):
        ids = [1, 2, 3]
        check_output.return_value = json.dumps(ids).encode('UTF-8')
        reltype = 'foo'
        relation_type.return_value = reltype

        result = hookenv.relation_ids()

        self.assertEqual(result, ids)
        check_output.assert_called_with(['relation-ids', '--format=json',
                                         reltype])

    @patch('subprocess.check_output')
    @patch('charmhelpers.core.hookenv.relation_type')
    def test_gets_relation_ids_empty_array(self, relation_type, check_output):
        ids = []
        check_output.return_value = json.dumps(None).encode('UTF-8')
        reltype = 'foo'
        relation_type.return_value = reltype

        result = hookenv.relation_ids()

        self.assertEqual(result, ids)
        check_output.assert_called_with(['relation-ids', '--format=json',
                                         reltype])

    @patch('subprocess.check_output')
    @patch('charmhelpers.core.hookenv.relation_type')
    def test_relation_ids_no_relation_type(self, relation_type, check_output):
        ids = [1, 2, 3]
        check_output.return_value = json.dumps(ids).encode('UTF-8')
        relation_type.return_value = None

        result = hookenv.relation_ids()

        self.assertEqual(result, [])

    @patch('subprocess.check_output')
    @patch('charmhelpers.core.hookenv.relation_type')
    def test_gets_relation_ids_for_type(self, relation_type, check_output):
        ids = [1, 2, 3]
        check_output.return_value = json.dumps(ids).encode('UTF-8')
        reltype = 'foo'

        result = hookenv.relation_ids(reltype)

        self.assertEqual(result, ids)
        check_output.assert_called_with(['relation-ids', '--format=json',
                                         reltype])
        self.assertFalse(relation_type.called)

    @patch('subprocess.check_output')
    @patch('charmhelpers.core.hookenv.relation_id')
    def test_gets_related_units(self, relation_id, check_output):
        relid = 123
        units = ['foo', 'bar']
        relation_id.return_value = relid
        check_output.return_value = json.dumps(units).encode('UTF-8')

        result = hookenv.related_units()

        self.assertEqual(result, units)
        check_output.assert_called_with(['relation-list', '--format=json',
                                         '-r', relid])

    @patch('subprocess.check_output')
    @patch('charmhelpers.core.hookenv.relation_id')
    def test_gets_related_units_empty_array(self, relation_id, check_output):
        relid = str(123)
        units = []
        relation_id.return_value = relid
        check_output.return_value = json.dumps(None).encode('UTF-8')

        result = hookenv.related_units()

        self.assertEqual(result, units)
        check_output.assert_called_with(['relation-list', '--format=json',
                                         '-r', relid])

    @patch('subprocess.check_output')
    @patch('charmhelpers.core.hookenv.relation_id')
    def test_related_units_no_relation(self, relation_id, check_output):
        units = ['foo', 'bar']
        relation_id.return_value = None
        check_output.return_value = json.dumps(units).encode('UTF-8')

        result = hookenv.related_units()

        self.assertEqual(result, units)
        check_output.assert_called_with(['relation-list', '--format=json'])

    @patch('subprocess.check_output')
    @patch('charmhelpers.core.hookenv.relation_id')
    def test_gets_related_units_for_id(self, relation_id, check_output):
        relid = 123
        units = ['foo', 'bar']
        check_output.return_value = json.dumps(units).encode('UTF-8')

        result = hookenv.related_units(relid)

        self.assertEqual(result, units)
        check_output.assert_called_with(['relation-list', '--format=json',
                                         '-r', relid])
        self.assertFalse(relation_id.called)

    @patch('charmhelpers.core.hookenv.os')
    def test_gets_the_remote_unit(self, os_):
        os_.environ = {
            'JUJU_REMOTE_UNIT': 'foo',
        }

        self.assertEqual(hookenv.remote_unit(), 'foo')

    @patch('charmhelpers.core.hookenv.os')
    def test_no_remote_unit(self, os_):
        os_.environ = {}
        self.assertEqual(hookenv.remote_unit(), None)

    @patch('charmhelpers.core.hookenv.remote_unit')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_gets_relation_for_unit(self, relation_get, remote_unit):
        unit = 'foo-unit'
        raw_relation = {
            'foo': 'bar',
        }
        remote_unit.return_value = unit
        relation_get.return_value = raw_relation

        result = hookenv.relation_for_unit()

        self.assertEqual(result['__unit__'], unit)
        self.assertEqual(result['foo'], 'bar')
        relation_get.assert_called_with(unit=unit, rid=None)

    @patch('charmhelpers.core.hookenv.remote_unit')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_gets_relation_for_unit_with_list(self, relation_get, remote_unit):
        unit = 'foo-unit'
        raw_relation = {
            'foo-list': 'one two three',
        }
        remote_unit.return_value = unit
        relation_get.return_value = raw_relation

        result = hookenv.relation_for_unit()

        self.assertEqual(result['__unit__'], unit)
        self.assertEqual(result['foo-list'], ['one', 'two', 'three'])
        relation_get.assert_called_with(unit=unit, rid=None)

    @patch('charmhelpers.core.hookenv.remote_unit')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_gets_relation_for_specific_unit(self, relation_get, remote_unit):
        unit = 'foo-unit'
        raw_relation = {
            'foo': 'bar',
        }
        relation_get.return_value = raw_relation

        result = hookenv.relation_for_unit(unit)

        self.assertEqual(result['__unit__'], unit)
        self.assertEqual(result['foo'], 'bar')
        relation_get.assert_called_with(unit=unit, rid=None)
        self.assertFalse(remote_unit.called)

    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_for_unit')
    def test_gets_relations_for_id(self, relation_for_unit, related_units,
                                   relation_ids):
        relid = 123
        units = ['foo', 'bar']
        unit_data = [
            {'foo-item': 'bar-item'},
            {'foo-item2': 'bar-item2'},
        ]
        relation_ids.return_value = relid
        related_units.return_value = units
        relation_for_unit.side_effect = unit_data

        result = hookenv.relations_for_id()

        self.assertEqual(result[0]['__relid__'], relid)
        self.assertEqual(result[0]['foo-item'], 'bar-item')
        self.assertEqual(result[1]['__relid__'], relid)
        self.assertEqual(result[1]['foo-item2'], 'bar-item2')
        related_units.assert_called_with(relid)
        self.assertEqual(relation_for_unit.mock_calls, [
            call('foo', relid),
            call('bar', relid),
        ])

    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_for_unit')
    def test_gets_relations_for_specific_id(self, relation_for_unit,
                                            related_units, relation_ids):
        relid = 123
        units = ['foo', 'bar']
        unit_data = [
            {'foo-item': 'bar-item'},
            {'foo-item2': 'bar-item2'},
        ]
        related_units.return_value = units
        relation_for_unit.side_effect = unit_data

        result = hookenv.relations_for_id(relid)

        self.assertEqual(result[0]['__relid__'], relid)
        self.assertEqual(result[0]['foo-item'], 'bar-item')
        self.assertEqual(result[1]['__relid__'], relid)
        self.assertEqual(result[1]['foo-item2'], 'bar-item2')
        related_units.assert_called_with(relid)
        self.assertEqual(relation_for_unit.mock_calls, [
            call('foo', relid),
            call('bar', relid),
        ])
        self.assertFalse(relation_ids.called)

    @patch('charmhelpers.core.hookenv.in_relation_hook')
    @patch('charmhelpers.core.hookenv.relation_type')
    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.relations_for_id')
    def test_gets_relations_for_type(self, relations_for_id, relation_ids,
                                     relation_type, in_relation_hook):
        reltype = 'foo-type'
        relids = [123, 234]
        relations = [
            [
                {'foo': 'bar'},
                {'foo2': 'bar2'},
            ],
            [
                {'FOO': 'BAR'},
                {'FOO2': 'BAR2'},
            ],
        ]
        is_in_relation = True

        relation_type.return_value = reltype
        relation_ids.return_value = relids
        relations_for_id.side_effect = relations
        in_relation_hook.return_value = is_in_relation

        result = hookenv.relations_of_type()

        self.assertEqual(result[0]['__relid__'], 123)
        self.assertEqual(result[0]['foo'], 'bar')
        self.assertEqual(result[1]['__relid__'], 123)
        self.assertEqual(result[1]['foo2'], 'bar2')
        self.assertEqual(result[2]['__relid__'], 234)
        self.assertEqual(result[2]['FOO'], 'BAR')
        self.assertEqual(result[3]['__relid__'], 234)
        self.assertEqual(result[3]['FOO2'], 'BAR2')
        relation_ids.assert_called_with(reltype)
        self.assertEqual(relations_for_id.mock_calls, [
            call(123),
            call(234),
        ])

    @patch('charmhelpers.core.hookenv.local_unit')
    @patch('charmhelpers.core.hookenv.relation_types')
    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_gets_relations(self, relation_get, related_units,
                            relation_ids, relation_types, local_unit):
        local_unit.return_value = 'u0'
        relation_types.return_value = ['t1', 't2']
        relation_ids.return_value = ['i1']
        related_units.return_value = ['u1', 'u2']
        relation_get.return_value = {'key': 'val'}

        result = hookenv.relations()

        self.assertEqual(result, {
            't1': {
                'i1': {
                    'u0': {'key': 'val'},
                    'u1': {'key': 'val'},
                    'u2': {'key': 'val'},
                },
            },
            't2': {
                'i1': {
                    'u0': {'key': 'val'},
                    'u1': {'key': 'val'},
                    'u2': {'key': 'val'},
                },
            },
        })

    @patch('charmhelpers.core.hookenv.relation_set')
    @patch('charmhelpers.core.hookenv.relation_get')
    @patch('charmhelpers.core.hookenv.local_unit')
    def test_relation_clear(self, local_unit,
                            relation_get,
                            relation_set):
        local_unit.return_value = 'local-unit'
        relation_get.return_value = {
            'private-address': '10.5.0.1',
            'foo': 'bar',
            'public-address': '146.192.45.6'
        }
        hookenv.relation_clear('relation:1')
        relation_get.assert_called_with(rid='relation:1',
                                        unit='local-unit')
        relation_set.assert_called_with(
            relation_id='relation:1',
            **{'private-address': '10.5.0.1',
               'foo': None,
               'public-address': '146.192.45.6'})

    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_is_relation_made(self, relation_get, related_units,
                              relation_ids):
        relation_get.return_value = 'hostname'
        related_units.return_value = ['test/1']
        relation_ids.return_value = ['test:0']
        self.assertTrue(hookenv.is_relation_made('test'))
        relation_get.assert_called_with('private-address',
                                        rid='test:0', unit='test/1')

    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_is_relation_made_multi_unit(self, relation_get, related_units,
                                         relation_ids):
        relation_get.side_effect = [None, 'hostname']
        related_units.return_value = ['test/1', 'test/2']
        relation_ids.return_value = ['test:0']
        self.assertTrue(hookenv.is_relation_made('test'))

    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_is_relation_made_different_key(self,
                                            relation_get, related_units,
                                            relation_ids):
        relation_get.return_value = 'hostname'
        related_units.return_value = ['test/1']
        relation_ids.return_value = ['test:0']
        self.assertTrue(hookenv.is_relation_made('test', keys='auth'))
        relation_get.assert_called_with('auth',
                                        rid='test:0', unit='test/1')

    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_is_relation_made_multiple_keys(self,
                                            relation_get, related_units,
                                            relation_ids):
        relation_get.side_effect = ['password', 'hostname']
        related_units.return_value = ['test/1']
        relation_ids.return_value = ['test:0']
        self.assertTrue(hookenv.is_relation_made('test',
                                                 keys=['auth', 'host']))
        relation_get.assert_has_calls(
            [call('auth', rid='test:0', unit='test/1'),
             call('host', rid='test:0', unit='test/1')]
        )

    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_is_relation_made_not_made(self,
                                       relation_get, related_units,
                                       relation_ids):
        relation_get.return_value = None
        related_units.return_value = ['test/1']
        relation_ids.return_value = ['test:0']
        self.assertFalse(hookenv.is_relation_made('test'))

    @patch('charmhelpers.core.hookenv.relation_ids')
    @patch('charmhelpers.core.hookenv.related_units')
    @patch('charmhelpers.core.hookenv.relation_get')
    def test_is_relation_made_not_made_multiple_keys(self,
                                                     relation_get,
                                                     related_units,
                                                     relation_ids):
        relation_get.side_effect = ['password', None]
        related_units.return_value = ['test/1']
        relation_ids.return_value = ['test:0']
        self.assertFalse(hookenv.is_relation_made('test',
                                                  keys=['auth', 'host']))
        relation_get.assert_has_calls(
            [call('auth', rid='test:0', unit='test/1'),
             call('host', rid='test:0', unit='test/1')]
        )

    @patch('charmhelpers.core.hookenv.config')
    @patch('charmhelpers.core.hookenv.relation_type')
    @patch('charmhelpers.core.hookenv.local_unit')
    @patch('charmhelpers.core.hookenv.relation_id')
    @patch('charmhelpers.core.hookenv.relations')
    @patch('charmhelpers.core.hookenv.relation_get')
    @patch('charmhelpers.core.hookenv.os')
    def test_gets_execution_environment(self, os_, relations_get,
                                        relations, relation_id, local_unit,
                                        relation_type, config):
        config.return_value = 'some-config'
        relation_type.return_value = 'some-type'
        local_unit.return_value = 'some-unit'
        relation_id.return_value = 'some-id'
        relations.return_value = 'all-relations'
        relations_get.return_value = 'some-relations'
        os_.environ = 'some-environment'

        result = hookenv.execution_environment()

        self.assertEqual(result, {
            'conf': 'some-config',
            'reltype': 'some-type',
            'unit': 'some-unit',
            'relid': 'some-id',
            'rel': 'some-relations',
            'rels': 'all-relations',
            'env': 'some-environment',
        })

    @patch('charmhelpers.core.hookenv.config')
    @patch('charmhelpers.core.hookenv.relation_type')
    @patch('charmhelpers.core.hookenv.local_unit')
    @patch('charmhelpers.core.hookenv.relation_id')
    @patch('charmhelpers.core.hookenv.relations')
    @patch('charmhelpers.core.hookenv.relation_get')
    @patch('charmhelpers.core.hookenv.os')
    def test_gets_execution_environment_no_relation(
            self, os_, relations_get, relations, relation_id,
            local_unit, relation_type, config):
        config.return_value = 'some-config'
        relation_type.return_value = 'some-type'
        local_unit.return_value = 'some-unit'
        relation_id.return_value = None
        relations.return_value = 'all-relations'
        relations_get.return_value = 'some-relations'
        os_.environ = 'some-environment'

        result = hookenv.execution_environment()

        self.assertEqual(result, {
            'conf': 'some-config',
            'unit': 'some-unit',
            'rels': 'all-relations',
            'env': 'some-environment',
        })

    @patch('charmhelpers.core.hookenv.os')
    def test_gets_the_relation_id(self, os_):
        os_.environ = {
            'JUJU_RELATION_ID': 'foo',
        }

        self.assertEqual(hookenv.relation_id(), 'foo')

    @patch('charmhelpers.core.hookenv.os')
    def test_relation_id_none_if_no_env(self, os_):
        os_.environ = {}
        self.assertEqual(hookenv.relation_id(), None)

    @patch('subprocess.check_output')
    def test_gets_relation(self, check_output):
        data = {"foo": "BAR"}
        check_output.return_value = json.dumps(data).encode('UTF-8')
        result = hookenv.relation_get()

        self.assertEqual(result['foo'], 'BAR')
        check_output.assert_called_with(['relation-get', '--format=json', '-'])

    @patch('charmhelpers.core.hookenv.subprocess')
    def test_relation_get_none(self, mock_subprocess):
        mock_subprocess.check_output.return_value = b'null'

        result = hookenv.relation_get()

        self.assertIsNone(result)

    @patch('charmhelpers.core.hookenv.subprocess')
    def test_relation_get_calledprocesserror(self, mock_subprocess):
        """relation-get called outside a relation will errors without id."""
        mock_subprocess.check_output.side_effect = CalledProcessError(
            2, '/foo/bin/relation-get'
            'no relation id specified')

        result = hookenv.relation_get()

        self.assertIsNone(result)

    @patch('charmhelpers.core.hookenv.subprocess')
    def test_relation_get_calledprocesserror_other(self, mock_subprocess):
        """relation-get can fail for other more serious errors."""
        mock_subprocess.check_output.side_effect = CalledProcessError(
            1, '/foo/bin/relation-get'
            'connection refused')

        self.assertRaises(CalledProcessError, hookenv.relation_get)

    @patch('subprocess.check_output')
    def test_gets_relation_with_scope(self, check_output):
        check_output.return_value = json.dumps('bar').encode('UTF-8')

        result = hookenv.relation_get(attribute='baz-scope')

        self.assertEqual(result, 'bar')
        check_output.assert_called_with(['relation-get', '--format=json',
                                         'baz-scope'])

    @patch('subprocess.check_output')
    def test_gets_missing_relation_with_scope(self, check_output):
        check_output.return_value = b""

        result = hookenv.relation_get(attribute='baz-scope')

        self.assertEqual(result, None)
        check_output.assert_called_with(['relation-get', '--format=json',
                                         'baz-scope'])

    @patch('subprocess.check_output')
    def test_gets_relation_with_unit_name(self, check_output):
        check_output.return_value = json.dumps('BAR').encode('UTF-8')

        result = hookenv.relation_get(attribute='baz-scope', unit='baz-unit')

        self.assertEqual(result, 'BAR')
        check_output.assert_called_with(['relation-get', '--format=json',
                                         'baz-scope', 'baz-unit'])

    @patch('charmhelpers.core.hookenv.local_unit')
    @patch('subprocess.check_call')
    @patch('subprocess.check_output')
    def test_relation_set_flushes_local_unit_cache(self, check_output,
                                                   check_call, local_unit):
        check_output.return_value = json.dumps('BAR').encode('UTF-8')
        local_unit.return_value = 'baz_unit'
        hookenv.relation_get(attribute='baz_scope', unit='baz_unit')
        hookenv.relation_get(attribute='bar_scope')
        self.assertTrue(len(hookenv.cache) == 2)
        check_output.return_value = ""
        hookenv.relation_set(baz_scope='hello')
        # relation_set should flush any entries for local_unit
        self.assertTrue(len(hookenv.cache) == 1)

    @patch('subprocess.check_output')
    def test_gets_relation_with_relation_id(self, check_output):
        check_output.return_value = json.dumps('BAR').encode('UTF-8')

        result = hookenv.relation_get(attribute='baz-scope', unit='baz-unit',
                                      rid=123)

        self.assertEqual(result, 'BAR')
        check_output.assert_called_with(['relation-get', '--format=json', '-r',
                                         123, 'baz-scope', 'baz-unit'])

    @patch('subprocess.check_output')
    @patch('subprocess.check_call')
    def test_sets_relation_with_kwargs(self, check_call_, check_output):
        hookenv.relation_set(foo="bar")
        check_call_.assert_called_with(['relation-set', 'foo=bar'])

    @patch('subprocess.check_output')
    @patch('subprocess.check_call')
    def test_sets_relation_with_dict(self, check_call_, check_output):
        hookenv.relation_set(relation_settings={"foo": "bar"})
        check_call_.assert_called_with(['relation-set', 'foo=bar'])

    @patch('subprocess.check_output')
    @patch('subprocess.check_call')
    def test_sets_relation_with_relation_id(self, check_call_, check_output):
        hookenv.relation_set(relation_id="foo", bar="baz")
        check_call_.assert_called_with(['relation-set', '-r', 'foo',
                                        'bar=baz'])

    @patch('subprocess.check_output')
    @patch('subprocess.check_call')
    def test_sets_relation_with_missing_value(self, check_call_, check_output):
        hookenv.relation_set(foo=None)
        check_call_.assert_called_with(['relation-set', 'foo='])

    @patch('os.remove')
    @patch('subprocess.check_output')
    @patch('subprocess.check_call')
    def test_relation_set_file(self, check_call, check_output, remove):
        """If relation-set accepts a --file parameter, it's used.

        Juju 1.23.2 introduced a --file parameter, which means you can
        pass the data through a file. Not using --file would make
        relation_set break if the relation data is too big.
        """
        # check_output(["relation-set", "--help"]) is used to determine
        # whether we can pass --file to it.
        check_output.return_value = "--file"
        hookenv.relation_set(foo="bar")
        check_output.assert_called_with(["relation-set", "--help"])
        # relation-set is called with relation-set --file <temp_file>
        # with data as YAML and the temp_file is then removed.
        self.assertEqual(1, len(check_call.call_args[0]))
        command = check_call.call_args[0][0]
        self.assertEqual(3, len(command))
        self.assertEqual("relation-set", command[0])
        self.assertEqual("--file", command[1])
        temp_file = command[2]
        with open(temp_file, "r") as f:
            self.assertEqual("{foo: bar}", f.read().strip())
        remove.assert_called_with(temp_file)

    def test_lists_relation_types(self):
        open_ = mock_open()
        open_.return_value = io.BytesIO(CHARM_METADATA)

        with patch('charmhelpers.core.hookenv.open', open_, create=True):
            with patch.dict('os.environ', {'CHARM_DIR': '/var/empty'}):
                reltypes = set(hookenv.relation_types())
        open_.assert_called_once_with('/var/empty/metadata.yaml')
        self.assertEqual(set(('testreqs', 'testprov', 'testpeer')), reltypes)

    def test_metadata(self):
        open_ = mock_open()
        open_.return_value = io.BytesIO(CHARM_METADATA)

        with patch('charmhelpers.core.hookenv.open', open_, create=True):
            with patch.dict('os.environ', {'CHARM_DIR': '/var/empty'}):
                metadata = hookenv.metadata()
        self.assertEqual(metadata, yaml.safe_load(CHARM_METADATA))

    def test_charm_name(self):
        open_ = mock_open()
        open_.return_value = io.BytesIO(CHARM_METADATA)

        with patch('charmhelpers.core.hookenv.open', open_, create=True):
            with patch.dict('os.environ', {'CHARM_DIR': '/var/empty'}):
                charm_name = hookenv.charm_name()
        self.assertEqual("testmock", charm_name)

    @patch('subprocess.check_call')
    def test_opens_port(self, check_call_):
        hookenv.open_port(443, "TCP")
        hookenv.open_port(80)
        hookenv.open_port(100, "UDP")
        calls = [
            call(['open-port', '443/TCP']),
            call(['open-port', '80/TCP']),
            call(['open-port', '100/UDP']),
        ]
        check_call_.assert_has_calls(calls)

    @patch('subprocess.check_call')
    def test_closes_port(self, check_call_):
        hookenv.close_port(443, "TCP")
        hookenv.close_port(80)
        hookenv.close_port(100, "UDP")
        calls = [
            call(['close-port', '443/TCP']),
            call(['close-port', '80/TCP']),
            call(['close-port', '100/UDP']),
        ]
        check_call_.assert_has_calls(calls)

    @patch('subprocess.check_output')
    def test_gets_unit_attribute(self, check_output_):
        check_output_.return_value = json.dumps('bar').encode('UTF-8')
        self.assertEqual(hookenv.unit_get('foo'), 'bar')
        check_output_.assert_called_with(['unit-get', '--format=json', 'foo'])

    @patch('subprocess.check_output')
    def test_gets_missing_unit_attribute(self, check_output_):
        check_output_.return_value = b""
        self.assertEqual(hookenv.unit_get('foo'), None)
        check_output_.assert_called_with(['unit-get', '--format=json', 'foo'])

    def test_cached_decorator(self):
        calls = []
        values = {
            'hello': 'world',
            'foo': 'bar',
            'baz': None,
        }

        @hookenv.cached
        def cache_function(attribute):
            calls.append(attribute)
            return values[attribute]

        self.assertEquals(cache_function('hello'), 'world')
        self.assertEquals(cache_function('hello'), 'world')
        self.assertEquals(cache_function('foo'), 'bar')
        self.assertEquals(cache_function('baz'), None)
        self.assertEquals(cache_function('baz'), None)
        self.assertEquals(calls, ['hello', 'foo', 'baz'])

    def test_gets_charm_dir(self):
        with patch.dict('os.environ', {'CHARM_DIR': '/var/empty'}):
            self.assertEqual(hookenv.charm_dir(), '/var/empty')

    @patch('subprocess.check_output')
    def test_is_leader_unsupported(self, check_output_):
        check_output_.side_effect = OSError(2, 'is-leader')
        self.assertRaises(NotImplementedError, hookenv.is_leader)

    @patch('subprocess.check_output')
    def test_is_leader(self, check_output_):
        check_output_.return_value = b'false'
        self.assertFalse(hookenv.is_leader())
        check_output_.return_value = b'true'
        self.assertTrue(hookenv.is_leader())


class HooksTest(TestCase):
    def setUp(self):
        super(HooksTest, self).setUp()
        self.config = patch.object(hookenv, 'config')
        self.config.start()

    def tearDown(self):
        super(HooksTest, self).tearDown()
        self.config.stop()

    def test_config_saved_after_execute(self):
        config = hookenv.config()
        config.implicit_save = True

        foo = MagicMock()
        hooks = hookenv.Hooks()
        hooks.register('foo', foo)
        hooks.execute(['foo', 'some', 'other', 'args'])

        self.assertTrue(config.save.called)

    def test_config_not_saved_after_execute(self):
        config = hookenv.config()
        config.implicit_save = False

        foo = MagicMock()
        hooks = hookenv.Hooks()
        hooks.register('foo', foo)
        hooks.execute(['foo', 'some', 'other', 'args'])

        self.assertFalse(config.save.called)

    def test_config_save_disabled(self):
        config = hookenv.config()
        config.implicit_save = True

        foo = MagicMock()
        hooks = hookenv.Hooks(config_save=False)
        hooks.register('foo', foo)
        hooks.execute(['foo', 'some', 'other', 'args'])

        self.assertFalse(config.save.called)

    def test_runs_a_registered_function(self):
        foo = MagicMock()
        hooks = hookenv.Hooks()
        hooks.register('foo', foo)

        hooks.execute(['foo', 'some', 'other', 'args'])

        foo.assert_called_with()

    def test_cannot_run_unregistered_function(self):
        foo = MagicMock()
        hooks = hookenv.Hooks()
        hooks.register('foo', foo)

        self.assertRaises(hookenv.UnregisteredHookError, hooks.execute,
                          ['bar'])

    def test_can_run_a_decorated_function_as_one_or_more_hooks(self):
        execs = []
        hooks = hookenv.Hooks()

        @hooks.hook('bar', 'baz')
        def func():
            execs.append(True)

        hooks.execute(['bar'])
        hooks.execute(['baz'])
        self.assertRaises(hookenv.UnregisteredHookError, hooks.execute,
                          ['brew'])
        self.assertEqual(execs, [True, True])

    def test_can_run_a_decorated_function_as_itself(self):
        execs = []
        hooks = hookenv.Hooks()

        @hooks.hook()
        def func():
            execs.append(True)

        hooks.execute(['func'])
        self.assertRaises(hookenv.UnregisteredHookError, hooks.execute,
                          ['brew'])
        self.assertEqual(execs, [True])

    def test_magic_underscores(self):
        # Juju hook names use hypens as separators. Python functions use
        # underscores. If explicit names have not been provided, hooks
        # are registered with both the function name and the function
        # name with underscores replaced with hypens for convenience.
        execs = []
        hooks = hookenv.Hooks()

        @hooks.hook()
        def call_me_maybe():
            execs.append(True)

        hooks.execute(['call-me-maybe'])
        hooks.execute(['call_me_maybe'])
        self.assertEqual(execs, [True, True])

    @patch('charmhelpers.core.hookenv.local_unit')
    def test_gets_service_name(self, _unit):
        _unit.return_value = 'mysql/3'
        self.assertEqual(hookenv.service_name(), 'mysql')

    @patch('subprocess.check_output')
    def test_action_get_with_key(self, check_output):
        action_data = 'bar'
        check_output.return_value = json.dumps(action_data).encode('UTF-8')

        result = hookenv.action_get(key='foo')

        self.assertEqual(result, 'bar')
        check_output.assert_called_with(['action-get', 'foo', '--format=json'])

    @patch('subprocess.check_output')
    def test_action_get_without_key(self, check_output):
        check_output.return_value = json.dumps(dict(foo='bar')).encode('UTF-8')

        result = hookenv.action_get()

        self.assertEqual(result['foo'], 'bar')
        check_output.assert_called_with(['action-get', '--format=json'])

    @patch('subprocess.check_call')
    def test_action_set(self, check_call):
        values = {'foo': 'bar', 'fooz': 'barz'}
        hookenv.action_set(values)
        # The order of the key/value pairs can change, so sort them before test
        called_args = check_call.call_args_list[0][0][0]
        called_args.pop(0)
        called_args.sort()
        self.assertEqual(called_args, ['foo=bar', 'fooz=barz'])

    @patch('subprocess.check_call')
    def test_action_fail(self, check_call):
        message = "Ooops, the action failed"
        hookenv.action_fail(message)
        check_call.assert_called_with(['action-fail', message])

    def test_status_set_invalid_state(self):
        self.assertRaises(ValueError, hookenv.status_set, 'random', 'message')

    @patch('subprocess.call')
    def test_status(self, call):
        call.return_value = 0
        hookenv.status_set('active', 'Everything is Awesome!')
        call.assert_called_with(['status-set', 'active', 'Everything is Awesome!'])

    @patch('subprocess.call')
    @patch.object(hookenv, 'log')
    def test_status_enoent(self, log, call):
        call.side_effect = OSError(2, 'fail')
        hookenv.status_set('active', 'Everything is Awesome!')
        log.assert_called_with('status-set failed: active Everything is Awesome!', level='INFO')

    @patch('subprocess.call')
    @patch.object(hookenv, 'log')
    def test_status_statuscmd_fail(self, log, call):
        call.side_effect = OSError(3, 'fail')
        self.assertRaises(OSError, hookenv.status_set, 'active', 'msg')
        call.assert_called_with(['status-set', 'active', 'msg'])

    @patch('subprocess.check_output')
    def test_status_get(self, check_output):
        check_output.return_value = 'active\n'
        result = hookenv.status_get()
        self.assertEqual(result, 'active')
        check_output.assert_called_with(['status-get'], universal_newlines=True)

    @patch('subprocess.check_output')
    def test_status_get_nostatus(self, check_output):
        check_output.side_effect = OSError(2, 'fail')
        result = hookenv.status_get()
        self.assertEqual(result, 'unknown')
        check_output.assert_called_with(['status-get'], universal_newlines=True)

    @patch('subprocess.check_output')
    def test_status_get_status_error(self, check_output):
        check_output.side_effect = OSError(3, 'fail')
        self.assertRaises(OSError, hookenv.status_get)
        check_output.assert_called_with(['status-get'], universal_newlines=True)
