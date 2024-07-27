from unittest.mock import Mock

from modules.inventory.group import Group, InvalidGroupMatch
from modules.inventory.host import Host

import pytest

class Test_Group:
    def test_same_should_return_true(self):
        name = "test1"
        test1 = Group(name = name)
        test2 = Group(name = name)
        assert test1.is_same(test2)
        test2.vars = {"thiskey": "doesn't exist in test1"}
        assert test1.is_same(test2)

    def test_same_should_return_false(self):
        test1 = Group(name = "test1")
        test2 = Group(name = "test2")
        assert not test1.is_same(test2)
        test1.vars = {"thiskey": "exists in both tests"}
        test2.vars = {"thiskey": "exists in both tests"}
        assert not test1.is_same(test2)

    def test_eq_should_return_true(self):
        name = "test1"
        test1 = Group(name = name)
        test2 = Group(name = name)
        assert test1 == test2
        test1.vars = {"thiskey": "exists in both"}
        test2.vars = {"thiskey": "exists in both"}
        assert test1 == test2
        test1.vars = {}
        test2.vars = {}
        test1.children = {"child1": Group(name = "child1")}
        test2.children = {"child1": Group(name = "child1")}
        assert test1 == test2
        test1.children = {}
        test2.children = {}
        test1.parents = {"parent1": Group(name = "parent1")}
        test2.parents = {"parent1": Group(name = "parent1")}
        assert test1 == test2
        test1.parents = {}
        test2.parents = {}
        test1.hosts = {'host1': Host("host1")}
        test2.hosts = {'host1': Host('host1')}
        assert test1 == test2

    def test_eq_should_return_false(self):
        test1 = Group(name = "test1")
        test2 = Group(name = "test2")
        assert test1 != test2
        test2.name = "test1"
        test1.vars = {"thiskey": "exists only in test1"}
        test2.vars = {"thiskey": "exists only in test2"}
        assert test1 != test2
        test1.vars = {}
        test2.vars = {}
        test1.children = {'child1': Group("child1")}
        test2.children = {'child2': Group("child2")}
        assert test1 != test2
        test1.children = {}
        test2.children = {}
        test1.parents = {'parent1': Group("parent1")}
        test2.parents = {'parent2': Group("parent2")}
        assert test1 != test2

    def test_should_add_variable(self):
        test = Group(name = "test")
        test.add_var("testvar", "testvalue")
        assert "testvar" in test.vars
        assert test.vars['testvar'] == "testvalue"

    def test_should_remove_variable(self):
        test = Group(name = "test", vars = {"testvar": "testvalue"})
        var = test.remove_var("testvar")
        assert var == "testvalue"
        assert "testvar" not in test.vars

    def test_should_add_parent(self):
        test = Group("test")
        test.add_parent(Group("parent"))
        assert "parent" in test.parents
        assert test.parents["parent"] == Group("parent", children=[test])
        assert "test" in test.parents['parent'].children
        parent = Group('test2')
        test = Group('test', parents=[parent])
        assert test.parents['test2'] == parent
        assert parent.children['test'] == test

    def test_should_remove_parent(self):
        test = Group(name = "test", parents=[Group("parent")])
        parent = test.remove_parent('parent')
        assert parent is not None
        assert isinstance(parent, Group)
        assert parent.name == 'parent'
        assert 'parent' not in test.parents
        assert 'test' not in parent.children

    def test_should_add_child(self):
        test = Group("test")
        test.add_child(Group("child"))
        assert "child" in test.children
        assert test.children["child"] == Group("child", parents=[test])
        assert "test" in test.children['child'].parents
        test = Group('test')
        parent = Group('test2', children=[test])
        assert parent.children['test'] == test
        assert test.parents['test2'] == parent

    def test_should_remove_child(self):
        test = Group(name = "test", children=[Group("child")])
        child = test.remove_child('child')
        assert child is not None
        assert isinstance(child, Group)
        assert child.name == 'child'
        assert 'child' not in test.children
        assert 'test' not in child.parents

    def test_should_add_host(self):
        test = Group("test")
        host = Host("host")
        test.add_host(host)
        assert "host" in test.hosts
        assert "test" in host.groups
        host = Host("host")
        test = Group('test', hosts=[host])
        assert 'host' in test.hosts
        assert 'test' in host.groups

    def test_should_remove_host(self):
        test = Group(name = "test", hosts=[Host("host")])
        host = test.remove_host('host')
        assert host is not None
        assert isinstance(host, Host)
        assert host.name == 'host'
        assert 'host' not in test.hosts
        assert "test" not in host.groups

    def test_merge_should_work(self):
        test_name = "test"
        test1_vars = {"key1": "value1"}
        test2_children = [Group(name = "test2_child")]
        test3_parents = [Group(name = "test3_parent")]
        test4_hosts = [Host("test4_host")]
        test5_vars = {"key2": "value2"}

        test1 = Group(name = test_name, vars = test1_vars)
        test2 = Group(name = test_name, children = test2_children)
        test3 = Group(name = test_name, parents = test3_parents)
        test4 = Group(name = test_name, hosts = test4_hosts)
        test5 = Group(name = test_name, vars = test5_vars)
        
        test1.merge(test2, test3, test4, test5)
        assert test1.vars == {
            "key1": "value1",
            "key2": "value2",
        }
        assert len(test1.children) == 1
        assert 'test2_child' in test1.children
        assert len(test1.parents) == 1
        assert 'test3_parent' in test1.parents
        assert len(test1.hosts) == 1
        assert 'test4_host' in test1.hosts

        test6 = Group(name = test_name, vars = {"key1": "value2"})
        test1.merge(test6)
        assert test1.vars == {
            "key1": "value2",
            "key2": "value2",
        }

    def test_merge_should_not_work(self):
        test_name = "test"
        test1_vars = {"key1": "value1"}
        test2_vars = {"key2": "value2"}
        test3_vars = {"key3": "value3"}

        test1 = Group(name = test_name, vars = test1_vars)
        test2 = Group(name = "test2", vars = test2_vars)
        test3 = Group(name = test_name, vars = test3_vars)

        with pytest.raises(InvalidGroupMatch):
            test1.merge(test2)

        with pytest.raises(InvalidGroupMatch):
            test1.merge(test3, test2)

        with pytest.raises(InvalidGroupMatch):
            test1.merge(test2, test3)

    def test_should_return_host(self):
        host = Host("host")
        test = Group(name = "test", hosts = [host])
        assert 'host' in test.hosts
        assert test.get_host('host') == host
        test.hosts = {}
        test.hosts = {'host': host}
        assert test.get_host('host') == host
        test.hosts = {}
        test.add_host(host)
        assert 'host' in test.hosts
        assert test.get_host('host') == host

    def test_should_not_return_host(self):
        test = Group(name = 'test')
        assert test.get_host('host') is None
        test.add_host(Host('host1'))
        assert test.get_host('host') is None

    def test_should_return_var(self):
        var = {'key': 'value'}
        test = Group(name = "test", vars = var)
        assert 'key' in test.vars
        assert test.get_var('key') == 'value'
        test.vars = {'key': 'value2'}
        assert test.get_var('key') == 'value2'
        test.vars = {}
        test.add_var('key', 'value3')
        assert 'key' in test.vars
        assert test.get_var('key') == 'value3'

    def test_should_not_return_var(self):
        test = Group(name = 'test')
        assert test.get_var('key') is None
        test.add_var('key', 'value')
        assert test.get_var('key2') is None

    def test_doesnt_self_merge_until_heat_death_of_universe(self):
        test = Group(name = "group")
        _ = Group(name = "parent", children=[test])
        _.merge(_)
        assert True
