from unittest.mock import Mock

from modules.inventory.host import InvalidHostMatch, Host
from modules.inventory.group import Group

import pytest

class Test_Host_Details:
    def test_same_should_return_true(self):
        hostname = "test1"
        test1 = Host(hostname)
        test2 = Host(hostname)
        assert test1.is_same(test2)
        test2.vars = {"thiskey": "doesn't exist in test1"}
        assert test1.is_same(test2)

    def test_add_group(self):
        test = Host("test")
        group = Group('group')
        test.add_group(group)
        assert 'test' in group.hosts
        assert 'group' in test.groups
        group = Group('group')
        test = Host('test', groups=[group])
        assert 'test' in group.hosts
        assert 'group' in test.groups

    def test_remove_group(self):
        test = Host("test")
        group = Group('group', hosts=[test])
        assert 'test' in group.hosts
        assert 'group' in test.groups
        test.remove_group('group')
        assert 'test' not in group.hosts
        assert 'group' not in test.groups
        group = Group('group')
        test = Host("test", groups=[group])
        assert 'test' in group.hosts
        assert 'group' in test.groups
        test.remove_group('group')
        assert 'test' not in group.hosts
        assert 'group' not in test.groups
        group = Group('group')
        test = Host('test')
        test.add_group(group)
        assert 'test' in group.hosts
        assert 'group' in test.groups
        test.remove_group('group')
        assert 'test' not in group.hosts
        assert 'group' not in test.groups

    def test_same_should_return_false(self):
        test1 = Host("test1")
        test2 = Host("test2")
        assert not test1.is_same(test2)
        test1.vars = {"thiskey": "exists in both tests"}
        test2.vars = {"thiskey": "exists in both tests"}
        assert not test1.is_same(test2)

    def test_eq_should_return_true(self):
        hostname = "test1"
        test1 = Host(hostname)
        test2 = Host(hostname)
        assert test1 == test2
        test2.vars = {"thiskey": "exists in both"}
        test1.vars = {"thiskey": "exists in both"}
        assert test1 == test2

    def test_eq_should_return_false(self):
        test1 = Host("test1")
        test2 = Host("test2")
        assert test1 != test2
        test2.name = "test1"
        test1.vars = {"thiskey": "exists only in test1"}
        test2.vars = {"thiskey": "exists only in test2"}
        assert test1 != test2

    def test_merge_should_work(self):
        test_hostname = "test"
        test1_vars = {"key1": "value1"}
        test2_vars = {"key2": "value2"}
        test3_vars = {"key3": "value3"}
        test4_vars = {"key4": "value4", "key5": "value5"}

        test1 = Host(test_hostname, vars = test1_vars)
        test2 = Host(test_hostname, vars = test2_vars)
        test3 = Host(test_hostname, vars = test3_vars)
        test4 = Host(test_hostname, vars = test4_vars)
        
        test1.merge(test2, test3, test4)
        assert test1.vars == {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
            "key4": "value4",
            "key5": "value5"
        }

        test5 = Host(test_hostname, vars = {"key1": "value2"})
        test1.merge(test5)
        assert test1.vars == {
            "key1": "value2",
            "key2": "value2",
            "key3": "value3",
            "key4": "value4",
            "key5": "value5"
        }

    def test_merge_should_not_work(self):
        test_hostname = "test"
        test1_vars = {"key1": "value1"}
        test2_vars = {"key2": "value2"}
        test3_vars = {"key3": "value3"}

        test1 = Host(test_hostname, vars = test1_vars)
        test2 = Host("test2", vars = test2_vars)
        test3 = Host(test_hostname, vars = test3_vars)

        with pytest.raises(InvalidHostMatch):
            test1.merge(test2)

        with pytest.raises(InvalidHostMatch):
            test1.merge(test3, test2)

        with pytest.raises(InvalidHostMatch):
            test1.merge(test2, test3)

    def test_should_add_variable(self):
        test = Host("test")
        test.add_var(key = "testvar", value = "testvalue")
        assert "testvar" in test.vars
        assert test.vars['testvar'] == "testvalue"

    def test_should_remove_variable(self):
        test = Host("test", vars = {"testvar": "testvalue"})
        var = test.remove_var(key = "testvar")
        assert var == "testvalue"
        assert "testvar" not in test.vars

    def test_should_return_var(self):
        var = {'key': 'value'}
        test = Host("test", vars = var)
        assert 'key' in test.vars
        assert test.get_var('key') == 'value'
        test.vars = {'key': 'value2'}
        assert test.get_var('key') == 'value2'
        test.vars = {}
        test.add_var('key', 'value3')
        assert 'key' in test.vars
        assert test.get_var('key') == 'value3'

    def test_should_not_return_var(self):
        test = Host('test')
        assert test.get_var('key') is None
        test.add_var('key', 'value')
        assert test.get_var('key2') is None

    def test_should_merge_groups(self):
        # TODO
        pass
