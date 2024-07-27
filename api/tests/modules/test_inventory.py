from pathlib import Path

from modules.inventory import Inventory, transpile_to_inventory, normalize_ini
from modules.inventory.group import Group
from modules.inventory.host import Host

import unittest.mock as um

class Test_Inventory:
    def it_should_not_have_any_groups(self):
        inv = Inventory()
        # Technically inventory will always have 2 groups, "all" and "ungrouped"
        assert len(inv.groups) == 2
        assert inv.get_group('all') is not None
        assert inv.get_group('ungrouped') is not None

    def it_should_have_groups(self):
        group = Group(name = 'test')
        inv = Inventory(groups = [group])
        # Technically inventory will always have 2 groups, "all" and "ungrouped"
        assert len(inv.groups) == 3
        assert inv.get_group('test') == group

    def it_should_add_group(self):
        inv = Inventory()
        test = inv.add_group("test")
        assert inv.get_group("test") == test
        assert len(inv.groups) == 3

    def it_should_remove_groups(self):
        inv = Inventory([Group('test')])
        inv.remove_group('test')
        assert inv.get_group('test') is None
        assert len(inv.groups) == 2
        inv.add_group('test2')
        inv.remove_group('test2')
        assert inv.get_group('test2') is None
        assert len(inv.groups) == 2

    def it_should_add_host(self):
        inv = Inventory()
        inv.add_host("test")
        assert 'test' in inv.groups['all'].hosts
        assert 'test' in inv.groups['ungrouped'].hosts
        inv.remove_host('test')
        inv.add_host('test2', 'group')
        assert 'test2' in inv.groups['all'].hosts
        assert 'test2' in inv.groups['group'].hosts
        assert 'test2' not in inv.groups['ungrouped'].hosts

    def it_should_remove_host(self):
        inv = Inventory()
        inv.add_host('test')
        inv.remove_host('test')
        assert 'test' not in inv.groups['all'].hosts
        inv.add_host('test2', 'group')
        assert 'test2' not in inv.groups['ungrouped'].hosts
        inv.remove_host_from_group('test2', 'group')
        assert 'test2' not in inv.groups['group'].hosts
        assert 'test2' in inv.groups['all'].hosts
        assert 'test2' in inv.groups['ungrouped'].hosts

    def it_should_return_group(self):
        test = Group(name = "test")
        inv = Inventory([test])
        assert inv.get_group('test') == test

    def it_should_not_return_group(self):
        inv = Inventory()
        assert inv.get_group('test') is None
        inv.add_group('test2')
        assert inv.get_group('test') is None

    def it_should_return_host(self):
        host = Host('test_host')
        test = Group(name = "test", hosts=[host])
        inv = Inventory([test])
        assert inv.get_host('test_host') == host
        inv = Inventory()
        inv._raw_add_group(test)
        assert inv.get_host('test_host') == host

    def it_should_not_return_host(self):
        inv = Inventory()
        assert inv.get_host('test_host') is None
        inv.add_host('test_host2')
        assert inv.get_host('test_host') is None
        inv.add_group('test_group')
        assert inv.get_host('test_host') is None

    def it_should_merge(self):
        inv1 = Inventory()
        inv2 = Inventory([Group(name = "test1")])
        inv3 = Inventory([Group(name = "test2")])
        inv4 = Inventory([Group(name = 'test2', vars={'key': 'value'})])
        assert 'test1' not in inv1.groups
        assert 'test2' not in inv1.groups
        inv1.merge(inv2, inv3, inv4)
        assert 'test1' in inv1.groups
        assert 'test2' in inv1.groups
        group = inv1.get_group('test2')
        assert 'key' in group.vars

class Test_Inventory_Transpiler:
    def it_should_transpile_vars_to_all(self):
        data = [
            {},
            {"key1": "value"},
            {"key2": "value2"}
        ]
        expected_data = {
            'key1': 'value',
            'key2': 'value2'
        }
        inv = transpile_to_inventory(flat_vars_group = data)
        assert inv.get_group('all').vars == expected_data

    def it_should_merge_vars_together(self):
        data = [
            {'key1': 'value'},
            {'key2': 'value2'},
            {'key1': 'value3'}
        ]
        expected_data = {
            'key1': 'value3',
            'key2': 'value2'
        }
        inv = transpile_to_inventory(flat_vars_group=data)
        assert inv.get_group('all').vars == expected_data

    def it_should_merge_ungrouped_hosts_together(self):
        data = [
            Host("test1"),
            Host("test1", vars={"key": "value"}),
            Host("test2")
        ]
        expected_data = {
            'test1': Host('test1', vars = {"key": "value"}),
            'test2': Host("test2")
        }
        inv = transpile_to_inventory(flat_hosts_group=data)
        assert inv.get_group('all').hosts == expected_data

    def it_should_merge_grouped_hosts_together(self):
        data = [
            Group("test", hosts=[Host("host", vars = {'key1': 'value1'})]),
            Group("test", hosts=[Host("host", vars = {"key2": "value2"})])
        ]
        inv = transpile_to_inventory(flat_groups_group=data)
        test = inv.get_group('test')
        assert test is not None
        host = test.get_host('host')
        assert host is not None
        assert host.get_var('key1') == 'value1'
        assert host.get_var('key2') == 'value2'

    def it_should_merge_grouped_and_ungrouped_hosts_together(self):
        group_data = [
            Group("group", hosts=[Host("host", vars = {'key1': 'value1'})]),
        ]
        host_data = [
             Host("host", vars = {"key2": "value2"})
        ]
        inv = transpile_to_inventory(flat_groups_group=group_data, flat_hosts_group=host_data)
        assert inv.get_group('group') is not None
        assert 'host' not in inv.get_group('ungrouped').hosts
        assert inv.get_group('group').get_host('host').vars == {'key1': 'value1', 'key2': 'value2'}

    def it_should_handle_complex_merging(self):
        data = {
            'flat_vars_group': [
                {
                    'ungrouped_var1': {'ungrouped_key': 'value1'},
                    'ungrouped_var2': {'ungrouped_key2': 'value2'}
                },
                {
                    'ungrouped_var1': {'ungrouped_key3': 'value3'},
                    'ungrouped_var2': {'ungrouped_key2': 'value4'}
                }
            ],
            'flat_hosts_group': [
                Host('ungrouped_host1'),
                Host('host1', vars = {'key': 'value'})
            ],
            'flat_groups_group': [
                Group('group1'),
                Group('group2', hosts=[Host('host1')]),
                Group('group1', parents=[Group('parent')])
            ]
        }
        expected_vars = {
            'ungrouped_var1': {'ungrouped_key': 'value1', 'ungrouped_key3': 'value3'},
            'ungrouped_var2': {'ungrouped_key2': 'value4'}
        }
        inv = transpile_to_inventory(**data)
        assert 'group1' in inv.groups
        assert 'group2' in inv.groups
        assert 'parent' in inv.groups
        assert 'host1' in inv.get_group('all').hosts
        assert 'host1' in inv.get_group('group2').hosts
        assert inv.get_host('host1') == Host('host1', vars = {'key': 'value'})
        assert inv.get_group('all').vars == expected_vars

# from pathlib import Path
# from unittest import mock as um
#
# import pytest
#
# from modules.inventory import (
#     Inventory,
#     normalize_ini_dict,
#     normalize_yaml_dict,
#     transpile_to_inventory,
# )
#
# # class Test_Inventory_Yaml_Load:
# #     def it_should_handle_multi_generational_children(self):
# #         mocked_data = {'group1': {'hosts': {'test1.com': None}, 'vars': {'hname': 'group1.example.com'}}, 'group2': {'hosts': 'test2.com', 'vars': {'hname': 'group2.example.com'}}, 'parent_group': {'children': {'group1': None, 'group2': None}}, 'grandparent_group': {'children': {'parent_group': None}}}
# #         expected_result = {
# #             'groups': {
# #                 'ungrouped': {},
# #                 'group1': {'hosts': {'test1.com': None}},
# #                 'group2': {'hosts': {'test2.com': None}},
# #                 'parent_group': {'children': {'group1': None, 'group2': None}},
# #                 'grandparent_group': {'children': {'parent_group': None}}
# #             },
# #             'vars': {
# #                 'host': {
# #                     'test1.com': {},
# #                     'test2.com': {}
# #                 },
# #                 'group': {
# #                     'group1': {'hname': 'group1.example.com'},
# #                     'group2': {'hname': 'group2.example.com'},
# #                     'parent_group': {},
# #                     'grandparent_group': {},
# #                 },
# #                 'ungrouped': {},
# #             },
# #         }
# #         actual_result = normalize_yaml_dict(mocked_data)
# #         assert(actual_result == expected_result)
#
#
# class Test_Inventory_Transpiler:
#     def it_should_return_default_dict(self):
#         mocked_data = [], [], []
#         expected_result = {
#             "groups": {"ungrouped": {}},
#             "vars": {"host": {}, "group": {}, "ungrouped": {}},
#         }
#         actual_result = transpile_to_inventory(*mocked_data)
#         assert actual_result == expected_result
#
#         mocked_data = {
#             "flat_vars_group": [],
#             "flat_hosts_group": [],
#             "flat_groups_group": [],
#         }
#         actual_result = transpile_to_inventory(**mocked_data)
#         assert actual_result == expected_result
#
#     def it_should_return_properly_merged_single_groups(self):
#         mocked_data = {
#             "flat_vars_group": [{'group1': {"var1": 1, "var2": 2}, 'group2': {"var3": 3, "var4": 4}}],
#             "flat_hosts_group": [],
#             "flat_groups_group": [],
#         }
#
#         expected_result = {
#             "groups": {"ungrouped": {}},
#             "vars": {
#                 "host": {},
#                 "group": {},
#                 "ungrouped": {'group1': {"var1": 1, "var2": 2}, 'group2': {"var3": 3, "var4": 4}},
#             },
#       }
#         actual_result = transpile_to_inventory(**mocked_data)
#         assert actual_result == expected_result
#
#
class Test_Inventory_Ini_Load:
    def scaffold(self, tmp_path: Path) -> dict[str, Path]:
        test_settings = {
            "inventory_location": tmp_path / "inventory",
            "playbook_location": tmp_path / "playbooks",
        }
        return test_settings

    def it_should_return_empty_dict(self):
        mocked_data = {}
        expected_result = {
            'flat_hosts': [],
            'flat_groups': [],
            'flat_vars': [{}]
        }
        actual_result = normalize_ini(mocked_data)
        assert actual_result == expected_result

    def it_should_return_ungrouped_host(self):
        mocked_data = {"test1.com": ""}
        expected_result = {
            'flat_hosts': [Host('test1.com')],
            'flat_groups': [],
            'flat_vars': [{}]
        }
        actual_result = normalize_ini(mocked_data)
        assert actual_result == expected_result

    def it_should_return_host_in_multiple_groups(self):
        mocked_data = {"group1": {"test1.com": ""}, "group2": {"test1.com": ""}}
        host = Host('test1.com')
        expected_result = {
            "flat_hosts": [host],
            'flat_groups': [
                Group('group1', hosts=[host]),
                Group('group2', hosts=[host])
            ],
            'flat_vars': [{}]
        }
        actual_result = normalize_ini(mocked_data)
        assert actual_result == expected_result

    # def it_should_correctly_merge_vars(self):
    # def it_should_properly_handle_no_default_tag(self):
    # def it_should_return_valid_dict(self):

    def it_should_handle_multi_generational_children(self):
        mocked_data = {
            "group1": {"test1.com": ""},
            "group2": {"test2.com": ""},
            "group1:vars": {"hname": "group1.example.com"},
            "group2:vars": {"hname": "group2.example.com"},
            "parent_group:children": {"group1": "", "group2": ""},
            "grandparent_group:children": {"parent_group": ""},
        }
        host1 = Host('test1.com')
        host2 = Host('test2.com')
        group1 = Group('group1', vars={'hname': 'group1.example.com'}, hosts = [host1])
        group2 = Group('group2', vars={'hname': 'group2.example.com'}, hosts = [host2])
        parent = Group('parent_group', children=[group1, group2])
        grandparent = Group('grandparent_group', children = [parent])
        actual_result = normalize_ini(mocked_data)
        assert host1 in actual_result['flat_hosts']
        assert host2 in actual_result['flat_hosts']
        assert group1 in actual_result['flat_groups']
        assert group2 in actual_result['flat_groups']
        assert parent in actual_result['flat_groups']
        assert grandparent in actual_result['flat_groups']
        assert actual_result['flat_vars'] == [{}]

    def it_should_handle_ungrouped_hosts(self, tmp_path):
        path = tmp_path / 'tmp' / 'hosts.ini'
        mocked_ini_data = '''exchange1.usa.com

[southwest:children]
california jump_server=usa.california.com
arizona
new_mexico

[california]
la-host1 jump_server=usa.california.com

[arizona:vars]
jump_server=usa.arizona.com
jump_user=texas
timeout=3000
app_restart=true
        '''
        inv: Inventory
        with um.patch('builtins.open', um.mock_open(read_data=mocked_ini_data)):
            inv = Inventory.load([Path(path)])
        la_host1 = inv.get_host('la-host1')
        assert la_host1 is not None
        assert la_host1.get_var('jump_server') == 'usa.california.com'
        assert inv.get_host('exchange1.usa.com') is not None
        california = inv.get_group('california')
        assert california is not None
        assert california.get_var('jump_server') == 'usa.california.com'
        assert inv.get_group('southwest') is not None
        assert inv.get_group('new_mexico') is not None
        
        arizona = inv.get_group('arizona')
        assert arizona is not None
        arizona: Group
        assert arizona.get_var('jump_server') == 'usa.arizona.com'
        assert arizona.get_var('jump_user') == 'texas'
        assert arizona.get_var('timeout') == 3000
        assert arizona.get_var('app_restart') == True
            # assert(actual_result == expected_result)

    # def it_should_not_recurse_forever(self):
    #     child1 = Group('child1')
    #     parent = Group('parent')
    #     parent.add_child(child1)
    #     inv = Inventory()
    #     for group in [parent, child1]:
    #         inv._raw_add_group(group)
    #     assert 'child1' in inv.groups
    #     assert 'parent' in inv.groups

    # def it_should_return_empty_dict(self, tmp_path: Path):
    #     inv: Inventory = self.scaffold(tmp_path)
    #     mocked_ini_data = ""
    #     expected_result = dict()
    #     path: Path = tmp_path / "tmp" / "hosts.ini"
    #     with um.patch("builtins.open", um.mock_open(read_data=mocked_ini_data)):
    #         actual_result = inv._Inventory__load_ini(path)
    #         assert actual_result == expected_result

    # def it_should_return_ungrouped_host(self, tmp_path: Path):
    #     inv: Inventory = self.scaffold(tmp_path)
    #     mocked_ini_data = 'test.com'
    #     expected_result = {
    #         'ungrouped': {
    #             'hosts': {'test.com': None}
    #         }
    #     }
    #     path = tmp_path / 'tmp' / 'hosts.ini'
    #     with um.patch('builtins.open', um.mock_open(read_data=mocked_ini_data)):
    #         actual_result = inv._Inventory__load_inventory_file_as_ini(path)
    #         assert(actual_result == expected_result)
    #
    # def it_should_return_grouped_host(self, tmp_path: Path):
    #     inv: Inventory = self.scaffold(tmp_path)
    #     mocked_ini_data = '''
    #     [group1]
    #     test.com
    #     '''
    #     expected_result = {
    #         'group1': {
    #             'hosts': {'test.com': None}
    #         }
    #     }
    #     path = tmp_path / 'tmp' / 'hosts.ini'
    #     with um.patch('builtins.open', um.mock_open(read_data=mocked_ini_data)):
    #         actual_result = inv._Inventory__load_inventory_file_as_ini(path)
    #         assert(actual_result == expected_result)
    #
    # def it_should_return_grouped_host_with_vars(self, tmp_path: Path):
    #     inv: Inventory = self.scaffold(tmp_path)
    #     mocked_ini_data = '''[group1]
    #     test.com
    #     [group1:vars]
    #     jump_server=test.com
    #     '''
    #     expected_result = {
    #         'group1': {
    #             'hosts': {'test.com': None},
    #             'vars': {
    #                 'jump-server': 'test.com'
    #             }
    #         }
    #     }
    #     path = tmp_path / 'tmp' / 'hosts.ini'
    #     with um.patch('builtins.open', um.mock_open(read_data=mocked_ini_data)):
    #         actual_result = inv._Inventory__load_inventory_file_as_ini(path)
    #         assert(actual_result == expected_result)
    #
    # def it_should_return_grouped_and_ungrouped_hosts(self, tmp_path: Path):
    #     inv: Inventory = self.scaffold(tmp_path)
    #     mocked_ini_data = '''test1.com
    #
    #     [group1]
    #     test2.com
    #     '''
    #     expected_result = {
    #         'group1': {
    #             'hosts': {'test2.com': None},
    #         },
    #         'ungrouped': {
    #             'hosts': {'test1.com': None}
    #         }
    #     }
    #     path = tmp_path / 'tmp' / 'hosts.ini'
    #     with um.patch('builtins.open', um.mock_open(read_data=mocked_ini_data)):
    #         actual_result = inv._Inventory__load_inventory_file_as_ini(path)
    #         assert(actual_result == expected_result)
    #
    # def it_should_return_grouped_children(self, tmp_path: Path):
    #     inv: Inventory = self.scaffold(tmp_path)
    #     mocked_ini_data = '''[group1]
    #     test1.com
    #
    #     [group2]
    #     test2.com
    #
    #     [parent_group:children]
    #     group1
    #     group2
    #     '''
    #     expected_result = {
    #         'group1': {
    #             'hosts': ['test1.com']
    #         },
    #         'group2': {
    #             'hosts': ['test2.com']
    #         },
    #         'parent_group': {
    #             'children': ['group1', 'group2']
    #         }
    #     }
    #     path = tmp_path / 'tmp' / 'hosts.ini'
    #     with um.patch('builtins.open', um.mock_open(read_data=mocked_ini_data)):
    #         actual_result = inv._Inventory__load_inventory_file_as_ini(path)
    #         assert(actual_result == expected_result)
    #
    # def it_should_return_nested_groups(self, tmp_path: Path):
    #     inv: Inventory = self.scaffold(tmp_path)
    #     mocked_ini_data = '''[group1]
    #     test1.com
    #
    #     [group2]
    #     test2.com
    #
    #     [parent_group:children]
    #     group1
    #     group2
    #
    #     [grandparent_group:children]
    #     parent_group
    #     '''
    #     expected_result = {
    #         'group1': {
    #             'hosts': ['test1.com']
    #         },
    #         'group2': {
    #             'hosts': ['test2.com']
    #         },
    #         'parent_group': {
    #             'children': ['group1', 'group2']
    #         },
    #         'grandparent_group': {
    #             'children': ['parent_group']
    #         }
    #     }
    #     path = tmp_path / 'tmp' / 'hosts.ini'
    #     with um.patch('builtins.open', um.mock_open(read_data=mocked_ini_data)):
    #         actual_result = inv._Inventory__load_inventory_file_as_ini(path)
    #         assert(actual_result == expected_result)
#
#
# # def test_02_load_inventory_file_as_yaml():
# #     assert 0 == 0
# #
# # def test_03_load_inventory_files():
# #     assert 0 == 0
# #
# # def test_04_import_existing_inventory():
# #     assert 0 == 0
# #
