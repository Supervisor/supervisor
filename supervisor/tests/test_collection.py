import unittest

from supervisor.tests.base import (
    DummyOptions,
    DummySupervisor,
    DummyPConfig,
    DummyPGroupConfig,
    DummyProcess,
    DummyProcessGroup,
)


class CollectionConfigTests(unittest.TestCase):

    def _getTargetClass(self):
        from supervisor.options import CollectionConfig
        return CollectionConfig

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_ctor(self):
        options = DummyOptions()
        config = self._makeOne(options, 'test', 999, ['prog1'], ['grp1'])
        self.assertEqual(config.name, 'test')
        self.assertEqual(config.priority, 999)
        self.assertEqual(config.program_names, ['prog1'])
        self.assertEqual(config.group_names, ['grp1'])

    def test_eq_equal(self):
        options = DummyOptions()
        c1 = self._makeOne(options, 'test', 999, ['prog1'], ['grp1'])
        c2 = self._makeOne(options, 'test', 999, ['prog1'], ['grp1'])
        self.assertEqual(c1, c2)

    def test_eq_different_name(self):
        options = DummyOptions()
        c1 = self._makeOne(options, 'test1', 999, ['prog1'], ['grp1'])
        c2 = self._makeOne(options, 'test2', 999, ['prog1'], ['grp1'])
        self.assertNotEqual(c1, c2)

    def test_eq_different_priority(self):
        options = DummyOptions()
        c1 = self._makeOne(options, 'test', 100, ['prog1'], ['grp1'])
        c2 = self._makeOne(options, 'test', 200, ['prog1'], ['grp1'])
        self.assertNotEqual(c1, c2)

    def test_eq_different_programs(self):
        options = DummyOptions()
        c1 = self._makeOne(options, 'test', 999, ['prog1'], [])
        c2 = self._makeOne(options, 'test', 999, ['prog2'], [])
        self.assertNotEqual(c1, c2)

    def test_eq_different_groups(self):
        options = DummyOptions()
        c1 = self._makeOne(options, 'test', 999, [], ['grp1'])
        c2 = self._makeOne(options, 'test', 999, [], ['grp2'])
        self.assertNotEqual(c1, c2)

    def test_eq_not_collection(self):
        options = DummyOptions()
        c1 = self._makeOne(options, 'test', 999, [], ['grp1'])
        self.assertNotEqual(c1, 'not a collection')

    def test_lt(self):
        options = DummyOptions()
        c1 = self._makeOne(options, 'test1', 100, [], ['grp1'])
        c2 = self._makeOne(options, 'test2', 200, [], ['grp1'])
        self.assertTrue(c1 < c2)
        self.assertFalse(c2 < c1)

    def test_sort(self):
        options = DummyOptions()
        c1 = self._makeOne(options, 'c', 300, [], ['grp1'])
        c2 = self._makeOne(options, 'a', 100, [], ['grp1'])
        c3 = self._makeOne(options, 'b', 200, [], ['grp1'])
        result = sorted([c1, c2, c3])
        self.assertEqual([c.name for c in result], ['a', 'b', 'c'])


class CollectionTests(unittest.TestCase):

    def _getTargetClass(self):
        from supervisor.collection import Collection
        return Collection

    def _makeOne(self, config, members):
        return self._getTargetClass()(config, members)

    def test_get_processes(self):
        from supervisor.options import CollectionConfig
        options = DummyOptions()
        config = CollectionConfig(options, 'test', 999, ['p1'], [])
        members = [('group1', 'proc1'), ('group2', 'proc2')]
        coll = self._makeOne(config, members)
        self.assertEqual(coll.get_processes(), members)

    def test_get_processes_returns_copy(self):
        from supervisor.options import CollectionConfig
        options = DummyOptions()
        config = CollectionConfig(options, 'test', 999, ['p1'], [])
        members = [('group1', 'proc1')]
        coll = self._makeOne(config, members)
        result = coll.get_processes()
        result.append(('extra', 'extra'))
        self.assertEqual(len(coll.get_processes()), 1)


class CollectionsFromParserTests(unittest.TestCase):

    def _getTargetClass(self):
        from supervisor.options import ServerOptions
        return ServerOptions

    def _makeOptions(self):
        options = self._getTargetClass()()
        options.here = '/tmp'
        return options

    def _makeParser(self, sections):
        """Create a fake parser with saneget support."""
        class FakeParser:
            def __init__(self, sections_dict):
                self._sections = sections_dict

            def sections(self):
                return list(self._sections.keys())

            def saneget(self, section, opt, default, **kwargs):
                return self._sections.get(section, {}).get(opt, default)
        return FakeParser(sections)

    def test_empty_config(self):
        options = self._makeOptions()
        parser = self._makeParser({})
        result = options.collections_from_parser(parser)
        self.assertEqual(result, [])

    def test_basic_collection_with_programs(self):
        options = self._makeOptions()
        parser = self._makeParser({
            'collection:web': {
                'programs': 'nginx,gunicorn',
                'priority': '100',
            }
        })
        result = options.collections_from_parser(parser)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, 'web')
        self.assertEqual(result[0].priority, 100)
        self.assertEqual(result[0].program_names, ['nginx', 'gunicorn'])
        self.assertEqual(result[0].group_names, [])

    def test_collection_with_groups(self):
        options = self._makeOptions()
        parser = self._makeParser({
            'collection:monitoring': {
                'groups': 'metrics,logging',
            }
        })
        result = options.collections_from_parser(parser)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, 'monitoring')
        self.assertEqual(result[0].group_names, ['metrics', 'logging'])
        self.assertEqual(result[0].program_names, [])

    def test_collection_with_both(self):
        options = self._makeOptions()
        parser = self._makeParser({
            'collection:mixed': {
                'programs': 'nginx',
                'groups': 'workers',
            }
        })
        result = options.collections_from_parser(parser)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].program_names, ['nginx'])
        self.assertEqual(result[0].group_names, ['workers'])

    def test_collection_neither_programs_nor_groups_raises(self):
        options = self._makeOptions()
        parser = self._makeParser({
            'collection:empty': {
                'priority': '100',
            }
        })
        with self.assertRaises(ValueError) as ctx:
            options.collections_from_parser(parser)
        self.assertIn('must specify at least one', str(ctx.exception))

    def test_collections_sorted_by_priority(self):
        options = self._makeOptions()
        parser = self._makeParser({
            'collection:low': {
                'programs': 'a',
                'priority': '300',
            },
            'collection:high': {
                'programs': 'b',
                'priority': '100',
            },
            'collection:mid': {
                'programs': 'c',
                'priority': '200',
            },
        })
        result = options.collections_from_parser(parser)
        self.assertEqual([c.name for c in result], ['high', 'mid', 'low'])

    def test_non_collection_sections_ignored(self):
        options = self._makeOptions()
        parser = self._makeParser({
            'program:foo': {'command': '/bin/foo'},
            'group:bar': {'programs': 'foo'},
            'collection:test': {'programs': 'foo'},
        })
        result = options.collections_from_parser(parser)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, 'test')


class SupervisordCollectionTests(unittest.TestCase):

    def _makeSupervisord(self):
        from supervisor.supervisord import Supervisor
        options = DummyOptions()
        options.collection_configs = []
        supervisord = Supervisor(options)
        return supervisord

    def _makeGroup(self, name, process_names):
        """Create a DummyProcessGroup with named processes."""
        options = DummyOptions()
        pconfigs = []
        for pname in process_names:
            pconfigs.append(DummyPConfig(options, pname, '/bin/%s' % pname))
        gconfig = DummyPGroupConfig(options, name, pconfigs=pconfigs)
        group = DummyProcessGroup(gconfig)
        group.processes = {}
        for pconfig in pconfigs:
            proc = DummyProcess(pconfig)
            group.processes[pconfig.name] = proc
        return group

    def _makeCollectionConfig(self, name, program_names=None,
                              group_names=None, priority=999):
        from supervisor.options import CollectionConfig
        options = DummyOptions()
        return CollectionConfig(options, name, priority,
                                program_names or [],
                                group_names or [])

    def test_resolve_collection_by_program_name(self):
        supervisord = self._makeSupervisord()
        group = self._makeGroup('workers', ['worker1', 'worker2'])
        supervisord.process_groups['workers'] = group

        config = self._makeCollectionConfig('test',
                                            program_names=['worker1'])
        coll = supervisord.resolve_collection(config)
        members = coll.get_processes()
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0][1].config.name, 'worker1')

    def test_resolve_collection_by_group_name(self):
        supervisord = self._makeSupervisord()
        group = self._makeGroup('workers', ['worker1', 'worker2'])
        supervisord.process_groups['workers'] = group

        config = self._makeCollectionConfig('test', group_names=['workers'])
        coll = supervisord.resolve_collection(config)
        members = coll.get_processes()
        self.assertEqual(len(members), 2)
        names = sorted([m[1].config.name for m in members])
        self.assertEqual(names, ['worker1', 'worker2'])

    def test_resolve_collection_deduplicates(self):
        supervisord = self._makeSupervisord()
        group = self._makeGroup('workers', ['worker1', 'worker2'])
        supervisord.process_groups['workers'] = group

        # Reference worker1 both by program name and by group
        config = self._makeCollectionConfig(
            'test',
            program_names=['worker1'],
            group_names=['workers']
        )
        coll = supervisord.resolve_collection(config)
        members = coll.get_processes()
        self.assertEqual(len(members), 2)  # worker1 + worker2, not 3

    def test_resolve_collection_missing_program_skipped(self):
        supervisord = self._makeSupervisord()
        group = self._makeGroup('workers', ['worker1'])
        supervisord.process_groups['workers'] = group

        config = self._makeCollectionConfig('test',
                                            program_names=['nonexistent'])
        coll = supervisord.resolve_collection(config)
        self.assertEqual(len(coll.get_processes()), 0)

    def test_resolve_collection_missing_group_skipped(self):
        supervisord = self._makeSupervisord()

        config = self._makeCollectionConfig('test',
                                            group_names=['nonexistent'])
        coll = supervisord.resolve_collection(config)
        self.assertEqual(len(coll.get_processes()), 0)

    def test_resolve_collection_across_groups(self):
        supervisord = self._makeSupervisord()
        group1 = self._makeGroup('web', ['nginx'])
        group2 = self._makeGroup('app', ['gunicorn'])
        supervisord.process_groups['web'] = group1
        supervisord.process_groups['app'] = group2

        config = self._makeCollectionConfig(
            'frontend',
            program_names=['nginx', 'gunicorn']
        )
        coll = supervisord.resolve_collection(config)
        members = coll.get_processes()
        self.assertEqual(len(members), 2)
        names = sorted([m[1].config.name for m in members])
        self.assertEqual(names, ['gunicorn', 'nginx'])

    def test_add_collection(self):
        supervisord = self._makeSupervisord()
        group = self._makeGroup('workers', ['worker1'])
        supervisord.process_groups['workers'] = group

        config = self._makeCollectionConfig('test',
                                            program_names=['worker1'])
        result = supervisord.add_collection(config)
        self.assertTrue(result)
        self.assertIn('test', supervisord.collections)

    def test_remove_collection(self):
        supervisord = self._makeSupervisord()
        group = self._makeGroup('workers', ['worker1'])
        supervisord.process_groups['workers'] = group

        config = self._makeCollectionConfig('test',
                                            program_names=['worker1'])
        supervisord.add_collection(config)
        self.assertIn('test', supervisord.collections)

        result = supervisord.remove_collection('test')
        self.assertTrue(result)
        self.assertNotIn('test', supervisord.collections)

    def test_diff_collections_to_active_added(self):
        supervisord = self._makeSupervisord()
        config = self._makeCollectionConfig('new', program_names=['p1'])
        supervisord.options.collection_configs = [config]

        added, changed, removed = supervisord.diff_collections_to_active()
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].name, 'new')
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 0)

    def test_diff_collections_to_active_removed(self):
        supervisord = self._makeSupervisord()
        config = self._makeCollectionConfig('old', program_names=['p1'])
        supervisord.add_collection(config)
        supervisord.options.collection_configs = []

        added, changed, removed = supervisord.diff_collections_to_active()
        self.assertEqual(len(added), 0)
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].name, 'old')

    def test_diff_collections_to_active_changed(self):
        supervisord = self._makeSupervisord()
        config1 = self._makeCollectionConfig('coll', program_names=['p1'])
        supervisord.add_collection(config1)

        config2 = self._makeCollectionConfig('coll', program_names=['p1', 'p2'])
        supervisord.options.collection_configs = [config2]

        added, changed, removed = supervisord.diff_collections_to_active()
        self.assertEqual(len(added), 0)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0].name, 'coll')
        self.assertEqual(len(removed), 0)


class CollectionEventsTests(unittest.TestCase):

    def test_collection_added_event(self):
        from supervisor.events import CollectionAddedEvent
        event = CollectionAddedEvent('test_coll')
        self.assertEqual(event.collection, 'test_coll')
        self.assertEqual(event.payload(), 'collectionname:test_coll\n')

    def test_collection_removed_event(self):
        from supervisor.events import CollectionRemovedEvent
        event = CollectionRemovedEvent('test_coll')
        self.assertEqual(event.collection, 'test_coll')
        self.assertEqual(event.payload(), 'collectionname:test_coll\n')


if __name__ == '__main__':
    unittest.main()
