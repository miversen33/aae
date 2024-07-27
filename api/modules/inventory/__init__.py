from __future__ import annotations

from functools import reduce
from pathlib import Path
from typing import Any, Iterable
import configparser
import re

import colorlog
import yaml

from modules import utils
from modules.utils import dict_deep_merge

from .host import Host
from .group import Group

IS_NUM_REGEX = re.compile(r'^\s*[.0-9]+\s*$')
IS_TRUE_REGEX = re.compile(r'^\s*true\s*$', re.IGNORECASE)
IS_FALSE_REGEX = re.compile(r'^\s*false\s*$', re.IGNORECASE)

def transpile_to_inventory(
    flat_vars_group: Iterable[dict[str, Any]] = list(),
    flat_hosts_group: Iterable[Host] = list(),
    flat_groups_group: Iterable[Group] = list()
) -> Inventory:
    inventory = Inventory()
    flat_vars: dict[str, Any] = {}
    if len(flat_hosts_group) > 0:
        [
            inventory._raw_add_host(host = host) for host in flat_hosts_group
        ]
    if len(flat_groups_group) > 0:
        [ inventory._raw_add_group(group = group) for group in flat_groups_group ]
    if len(flat_vars_group) > 0:
        flat_vars = reduce(lambda parent, child: dict_deep_merge(parent, child, utils.MergePolicy.ACCEPT_RIGHT), flat_vars_group)
        [ inventory.add_group_var('all', key, value) for key, value in flat_vars.items() ]
    return inventory

def normalize_yaml(yaml_as_dict: dict) -> dict[str, list[Host]|list[Group]|list[dict[str, Any]]]:
    flat_hosts: dict[str, Host] = {}
    flat_groups: dict[str, Group] = {}

    keys = ['all']
    mapping  = {'all': yaml_as_dict}
    while len(keys) > 0:
        key = keys.pop()
        raw_group = mapping[key]
        if key not in flat_groups:
            flat_groups[key] = Group(key)
        group = flat_groups[key]
        if raw_group is None:
            if key not in flat_groups:
                flat_groups[key] = Group(key)
        elif raw_group and 'hosts' not in raw_group and 'children' not in raw_group and 'vars' not in raw_group:
                for item_name, item in raw_group.items():
                    if item_name not in keys:
                        keys.append(item_name)
                    if item_name not in mapping:
                        mapping[item_name] = item
        else:
            if 'hosts' in raw_group:
                for hostname, hostdetails in raw_group['hosts'].items():
                    if hostname not in flat_hosts:
                        flat_hosts[hostname] = Host(hostname)
                    host = flat_hosts[hostname]
                    if isinstance(hostdetails, dict):
                        # there are host vars associated with this host
                        [host.add_var(host_var_key, host_var_value) for host_var_key, host_var_value in hostdetails.items()]
                    group.add_host(host)
            if 'children' in raw_group:
                for childgroup_name, childgroup_details in raw_group['children'].items():
                    if childgroup_name not in flat_groups:
                        flat_groups[childgroup_name] = Group(childgroup_name)
                    childgroup = flat_groups[childgroup_name]
                    group.add_child(childgroup)
                    mapping[childgroup_name] = childgroup_details
                    keys.append(childgroup_name)
            if 'vars' in raw_group:
                [group.add_var(group_var_key, group_var_value) for group_var_key, group_var_value in raw_group['vars'].items()]
        del mapping[key]
    del flat_groups['all']
    return {
        'flat_hosts': list(flat_hosts.values()),
        'flat_groups': list(flat_groups.values()),
        'flat_vars': []
    }

def normalize_ini(ini_as_dict: dict) -> dict[str, list[Host]|list[Group]|list[dict[str, Any]]]:
    logger = colorlog.getLogger()
    flat_hosts: dict[str, Host] = {}
    flat_groups: dict[str, Group] = {}
    flat_vars: dict[str, dict] = {}

    def clean_var(var: str) -> Any:
        if not isinstance(var, str):
            return var
        if IS_NUM_REGEX.match(var):
            if '.' in var:
                return float(var)
            else:
                return int(var)
        elif IS_TRUE_REGEX.match(var):
            return True
        elif IS_FALSE_REGEX.match(var):
            return False
        elif len(var) == 0:
            return None
        return var

    def handle_inline_vars(key: str, value: str) -> tuple[str, dict[str, str]]:
        inline_vars = {}
        key= re.sub(r'\s+', ' ', key)
        key, lead_var_name = key.split(' ')
        raw_inline_vars = f'{lead_var_name}={value}'
        for var in raw_inline_vars.split(' '):
            var_key, var_value = var.split('=')
            inline_vars[var_key] = clean_var(var_value)
        return key, inline_vars

    proc_queue: list[dict[str, Any]] = [ini_as_dict]
    while len(proc_queue) > 0:
        proc_item = proc_queue.pop()
        for key, value in proc_item.items():
            if ":" not in key:
                if isinstance(value, dict):
                    if key not in flat_groups:
                        flat_groups[key] = Group(name=key)
                    group = flat_groups[key]
                    for host_name in value.keys():
                        additional_vars = {}
                        if ' ' in host_name:
                            host_name, additional_vars = handle_inline_vars(host_name, value[host_name])
                        if host_name not in flat_hosts:
                            flat_hosts[host_name] = Host(host_name)
                        host = flat_hosts[host_name]
                        [host.add_var(child_host_key, clean_var(child_host_var)) for child_host_key, child_host_var in additional_vars.items()]
                        group.add_host(host)
                else:
                    flat_hosts[key] = Host(key)
            else:
                item_name, item_subname = key.split(":")
                if item_subname == "vars":
                    if item_name in flat_groups:
                        for var_name, var_value in value.items():
                            flat_groups[item_name].add_var(var_name, clean_var(var_value))
                    else:
                        flat_vars[item_name] = value
                elif item_subname == "children":
                    if item_name not in flat_groups:
                        flat_groups[item_name] = Group(name=item_name)
                    parent_group = flat_groups[item_name]
                    for child_group_name in value.keys():
                        additional_child_vars = {}
                        if " " in child_group_name:
                            child_group_vars = value[child_group_name]
                            child_group_name, additional_child_vars = handle_inline_vars(child_group_name, child_group_vars)
                            # this group has variables!
                        if child_group_name not in flat_groups:
                            flat_groups[child_group_name] = Group(
                                name=child_group_name
                            )
                        child_group = flat_groups[child_group_name]
                        [child_group.add_var(child_group_key, child_group_var) for child_group_key, child_group_var in additional_child_vars.items()]


                        # the add_child method joins the parent and 
                        # children together. There is no need to call
                        # add_parent as well, so we chose to call
                        # add_child as its more explicit considering
                        # we are processing the parent as opposed
                        # to the child
                        parent_group.add_child(child_group)
                else:
                    logger.warning(f'unable to process key: "{key}" as it does not meet the ansible ini key criteria. It must either define a group, or or vars/children of that group')
                    continue
    return {
        'flat_hosts': list(flat_hosts.values()),
        'flat_groups': list(flat_groups.values()),
        'flat_vars': [flat_vars]
    }

class InventoryLoadException(Exception):
    def __init__(self):
        super().__init__("Unable to load inventory, no load files provided!")

class Inventory:
    groups: dict[str, Group]

    def __init__(self, groups: list[Group] = list()):
        self.groups = {
            'all': Group(name = 'all'),
            'ungrouped': Group(name = 'ungrouped')
        }
        [ self._raw_add_group(group) for group in groups ]

    def _raw_add_group(self, group: Group):
        logger = colorlog.getLogger()
        groups = { group.name: group }
        group_keys = [group.name]
        index = 0
        while index < len(group_keys):
            proc_group = groups[group_keys[index]]
            for parent in proc_group.parents.values():
                if parent.name not in group_keys:
                    group_keys.append(parent.name)
                groups[parent.name] = parent
            for child in proc_group.children.values():
                if child.name not in group_keys:
                    group_keys.append(child.name)
                groups[child.name] = child
            index += 1
        for group in groups.values():
            logger.info(f"adding group {group.name} to inventory")
            if group.name in self.groups:
                self.groups[group.name].merge(group)
            else:
                self.groups[group.name] = group
            all_group: Group = self.get_group('all')
            if group.name != 'all' and group.name not in all_group.children:
                all_group.add_child(group)
            ungrouped_group: Group = self.get_group('ungrouped')
            for host in group.hosts.values():
                all_group.add_host(host)
                if group.name not in ['all', 'ungrouped']:
                    ungrouped_group.remove_host(host.name)
                # Merging the host item so they are the "same"
                # WARN: This is probably pretty shitty for memory...
                group.add_host(all_group.get_host(host.name), _add_self_to_host = False)

    def add_group(self, group_name: str) -> Group:
        if group_name in self.groups:
            return self.groups[group_name]
        group = Group(name = group_name)
        self._raw_add_group(group)
        return group

    def remove_group(self, group_name: str) -> Group|None:
        if group_name not in self.groups:
            return
        logger = colorlog.getLogger()
        logger.info(f'removing group {group_name} from inventory')
        return self.groups.pop(group_name)

    def get_groups(self) -> list[Group]:
        return [group for group in self.groups.values()]

    def get_group(self, group_name: str) -> Group|None:
        return self.groups.get(group_name, None)

    def add_host_to_group(self, host_name: str, group_name: str):
        host = self.get_group('all').get_host(host_name) or Host(host_name)
        self._raw_add_host_to_group(host, group_name = group_name)

    def add_host(self, host_name: str, *groups: str):
        host = self.get_group('all').get_host(host_name) or Host(host_name)
        self._raw_add_host(host, *groups)

    def _raw_add_host_to_group(self, host: Host, group_name: str):
        logger = colorlog.getLogger()
        logger.info(f"adding host {host.name} to group {group_name} in inventory")
        if group_name not in self.groups:
            self.add_group(group_name)
        group: Group = self.get_group(group_name)
        group.add_host(host)
        host_grouped = False
        for _group_name, group in self.groups.items():
            if _group_name in ['all', 'ungrouped']:
                continue
            if host.name in group.hosts:
                host_grouped = True
                break
        if group_name not in ['all', 'ungrouped'] or host_grouped:
            self.groups['ungrouped'].remove_host(host.name)
        elif not host_grouped:
            self.groups['ungrouped'].add_host(host)
        if group_name != 'all':
            self.groups['all'].add_host(host)

    def _raw_add_host(self, host: Host, *groups: str):
        logger = colorlog.getLogger()
        logger.info(f"adding host {host.name} to inventory")
        groups = set(groups)
        groups.add('all')
        groups: set[str]
        [ self._raw_add_host_to_group(host, group_name) for group_name in groups ]

    def remove_host_from_group(self, host_name: str, group_name: str, check_ungrouped: bool = True):
        logger = colorlog.getLogger()
        if group_name not in self.groups:
            logger.info(f"request to remove host {host_name} from group {group_name} impossible as group is not currently in tracked inventory!")
            return
        logger.debug(f"removing host {host_name} from group {group_name} in inventory")
        group: Group = self.get_group(group_name)
        group.remove_host(host_name)
        if not check_ungrouped:
            return
        ungrouped = True
        for _group in self.groups.values():
            if _group.name in ['all', 'ungrouped']:
                continue
            if host_name in _group.hosts:
                ungrouped = False
                break
        if ungrouped:
            logger.debug(f"orphaned host {host_name} being added to ungrouped group in inventory")
            self.add_host_to_group(host_name, 'ungrouped')

    def remove_host(self, host_name: str):
        logger = colorlog.getLogger()
        logger.warning(f"purging {host_name} from inventory")
        [ self.remove_host_from_group(host_name, group_name, False) for group_name in self.groups.keys() ]
        self.get_group('ungrouped').remove_host(host_name)
        self.get_group('all').remove_host(host_name)

    def add_host_var(self, host_name: str, host_var_key: str, host_var_value: Any):
        logger = colorlog.getLogger()
        logger.debug(f"adding host variable {host_var_key} to {host_name}")
        host: Host = self.get_group('all').get_host(host_name)
        if not host:
            logger.warning(f"host {host_name} not currently tracked. Adding it now, why you no do this???")
            host = self.add_host(host_name)
        host.add_var(host_var_key, host_var_value)

    def get_hosts(self) -> list[Host]:
        return self.get_group('all').get_hosts()

    def get_host(self, host_name: str) -> Host|None:
        return self.get_group('all').get_host(host_name)

    def get_host_var(self, host_name: str, host_var_key: str) -> Any:
        host: Host = self.get_group('all').get_host(host_name)
        if not host:
            return
        return host.get_var(host_var_key)

    def remove_host_var(self, host_name: str, host_var_key: str) -> Any:
        logger = colorlog.getLogger()
        logger.debug(f"removing host variable {host_var_key} from {host_name}")
        host: Host = self.get_group('all').get_host(host_name)
        if not host:
            return
        return host.remove_var(host_var_key)

    def add_group_var(self, group_name: str, group_var_key: str, group_var_value: Any):
        logger = colorlog.getLogger()
        logger.debug(f"adding group variable {group_var_key} to {group_name}")
        group: Group = self.get_group(group_name)
        if not group:
            logger.warning(f"group {group_name} not currently tracked. Adding it now, why you no do this???")
            group = self.add_group(group_name)
        group.add_var(group_var_key,group_var_value)

    def get_group_var(self, group_name: str, group_var_key: str) -> Any:
        group: Group = self.get_group(group_name)
        if not group:
            return
        return group.get_var(group_var_key)

    def remove_group_var(self, group_name: str, group_var_key: str) -> Any:
        group: Group = self.get_group(group_name)
        if not group:
            return
        return group.remove_var(group_var_key)

    def add_group_to_group(self, parent_group_name: str, child_group_name: str):
        parent: Group = self.get_group(parent_group_name)
        if not parent:
            parent = self.add_group(parent_group_name)
        child: Group = self.get_group(child_group_name)
        if not child:
            child = self.add_group(child_group_name)
        parent.add_child(child)
        #this line _should_ be redundant but for clarity we are going to keep it
        child.add_parent(parent)

    def remove_child_group_from_parent(self, parent_group_name: str, child_group_name: str) -> None:
        logger = colorlog.getLogger()
        parent: Group = self.get_group(parent_group_name)
        if not parent:
            logger.info(f"request to remove group {child_group_name} from group {parent_group_name} is impossible as parent group isn't currently tracked in inventory!")
            return
        child: Group = self.get_group(child_group_name)
        if not child:
            logger.info(f"request to remove group {child_group_name} from group {parent_group_name} is impossible as child group isn't currently tracked in inventory!")
            return
        logger.info(f"removing group {child_group_name} from group {parent_group_name}")
        parent.remove_child(child_group_name)
        #this line _should_ be redundant but for clarify we are going to keep it
        child.remove_parent(parent_group_name)

    def merge(self, *invs: 'Inventory'):
        if not invs or len(invs) == 0:
            return
        for inv in invs:
            if inv == self:
                # nothing to do here, we are already the same
                continue
            # We should probably store the name of the file(s) loaded into this inventory object
            for group_name, group in inv.groups.items():

                if group_name in self.groups:
                    self.get_group(group_name).merge(group)
                else:
                    self._raw_add_group(group)

    async def save(self, out_dir: Path):
        logger = colorlog.getLogger()

        hosts_file = out_dir / 'hosts'
        group_dir = out_dir / 'group_vars'
        hosts_dir = out_dir / 'host_vars'
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            hosts_file.touch()
            group_dir.mkdir(parents=True, exist_ok=True)
            hosts_dir.mkdir(parents=True, exist_ok=True)
            _ = group_dir / '.test'
            _.touch()
            _.unlink()
            _ = hosts_dir / '.test'
            _.touch()
            _.unlink()
        except PermissionError as exception:
            logger.debug(repr(exception))
            logger.error(exception)
            logger.critical(f'Received permission error while trying to create {out_dir.absolute()}')
            return
        except FileExistsError as exception:
            logger.debug(repr(exception))
            logger.error(exception)
            logger.critical(f'{out_dir.absolute()} is a file??')
            return

        def serialize_group(group: Group, dump_group_name: bool = True):
            with open(hosts_file, 'a') as _out_file:
                did_write = False
                if len(group.hosts) > 0:
                    if dump_group_name:
                        did_write = True
                        _out_file.write(f'[{group.name}]\n')
                    for host in group.get_hosts():
                        did_write = True
                        _out_file.write(f'{host.name}\n')
                        host_vars_file = hosts_dir / f'{host.name}.yaml'
                        if len(host.vars) > 0:
                            with open(host_vars_file, 'w') as _host_vars_out_file:
                                _host_vars_out_file.write('---\n')
                                yaml.safe_dump(host.vars, _host_vars_out_file)
                        elif host_vars_file.exists():
                            logger.debug(f"removing previously defined host vars file {host_vars_file.absolute()}")
                            try:
                                host_vars_file.unlink(missing_ok=True)
                            except PermissionError as exception:
                                logger.debug(repr(exception))
                                logger.error(exception)
                                logger.critical(f"unable to remove orphaned host_vars_file: {host_vars_file.absolute()}")
                if dump_group_name:
                    if len(group.children) > 0:
                        did_write = True
                        _out_file.write(f'[{group.name}:children]\n')
                        _out_file.writelines([f'{child.name}\n' for child in group.get_children()])
                    group_vars_file = group_dir / f'{group.name}.yaml'
                    if len(group.vars) > 0:
                        with open(group_vars_file, 'w') as _group_vars_out_file:
                            _group_vars_out_file.write('---\n')
                            yaml.safe_dump(group.vars, _group_vars_out_file)
                    else:
                        logger.debug(f"removing previously defined group vars file {group_vars_file.absolute()}")
                        try:
                            group_vars_file.unlink(missing_ok=True)
                        except PermissionError as exception:
                            logger.debug(repr(exception))
                            logger.error(exception)
                            logger.critical(f"unable to remove orphaned group_vars_file: {group_vars_file.absolute()}")
                if did_write:
                    _out_file.write("\n")

        if ungrouped := self.get_group('ungrouped'):
            if len(ungrouped.hosts) > 0:
                serialize_group(ungrouped, False)
        [serialize_group(group) for group in self.get_groups() if group.name not in ['all', 'ungrouped']]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        inv = {
            'groups': {},
            'hosts': {}
        }
        for group in self.get_groups():
            if group.name in ['all']:
                continue
            if group.name not in inv['groups']:
                inv['groups'][group.name] = {}
            inv_group = inv['groups'][group.name]
            if len(group.children) > 0 and 'children' not in inv_group:
                inv_group['children'] = []
            [inv_group['children'].append(child.name) for child in group.get_children()]
            if len(group.hosts) > 0 and 'hosts' not in inv_group:
                inv_group['hosts'] = []
            [inv_group['hosts'].append(host.name) for host in group.get_hosts()]
            if len(group.vars) > 0 and 'vars' not in inv_group:
                inv_group['vars'] = {}
            for key, value in group.vars.items():
                inv_group['vars'][key] = value
        for host in self.get_group('all').get_hosts():
            if host.name not in inv['hosts']:
                inv['hosts'][host.name] = {}
            inv_host = inv['hosts'][host.name]
            if len(host.vars) > 0 and 'vars' not in inv_host:
                inv_host['vars'] = {}
            for key, value in host.vars.items():
                inv_host['vars'][key] = value
        return inv

    @staticmethod
    def _load_from_ini(ini_files: list[Path]) -> tuple['Inventory', list[Path]]:
        logger = colorlog.getLogger()
        flat_vars_group = []
        flat_hosts_group = []
        flat_groups_group = []
        out_files = []
        for ini in ini_files:
            if ini not in out_files:
                out_files.append(ini)
            if ini.suffix not in ['', '.ini']:
                logger.debug(f"ignoring {ini.absolute} as its not an ini file")
                continue
            logger.debug(f"loading ini file: {ini.absolute()}")
            _raw_ini: configparser.ConfigParser
            with open(ini, 'r') as _in_file:
                _raw_ini = configparser.ConfigParser(allow_no_value=True)
                _lines = ''.join(_in_file.readlines()).lstrip()
                if not _lines.startswith('['): # ] stop fucking with my indent...
                    _lines = '[ungrouped]\n' + _lines
                _raw_ini.read_string(_lines)
            if _raw_ini is None:
                logger.warning(f"No data returned when trying to parse {ini.absolute()} as an ini!")
                continue
            if ini in out_files:
                out_files.remove(ini)
            ini_as_dict = {section: dict(_raw_ini.items(section)) for section in _raw_ini.sections()}
            normalized_ini = normalize_ini(ini_as_dict)
            flat_vars_group.extend(normalized_ini['flat_vars'])
            flat_hosts_group.extend(normalized_ini['flat_hosts'])
            flat_groups_group.extend(normalized_ini['flat_groups'])
        return transpile_to_inventory(flat_vars_group=flat_vars_group, flat_hosts_group=flat_hosts_group, flat_groups_group=flat_groups_group), out_files

    @staticmethod
    def _load_from_yaml(yaml_files: list[Path]) -> tuple['Inventory', list[Path]]:
        logger = colorlog.getLogger()
        flat_vars_group = []
        flat_hosts_group = []
        flat_groups_group = []
        out_files = []
        for file in yaml_files:
            if file not in out_files:
                out_files.append(file)
            # because yaml will parse damn near anything, we can't (or shouldn't)
            # limit based on suffix. This is unfortunate because
            # we _should_ be limiting this to yaml files only
            logger.debug(f"loading yaml file: {file.absolute()}")
            _raw_yaml: dict[str, Any]
            with open(file, 'r') as _in_file:
                _raw_yaml = yaml.safe_load(_in_file)
            if not _raw_yaml:
                logger.info(f"yaml file: {file.absolute()} is apparently empty??")
                continue
            if file in out_files:
                out_files.remove(file)
            normalized_yaml = normalize_yaml(_raw_yaml)
            flat_vars_group.extend(normalized_yaml['flat_vars'])
            flat_groups_group.extend(normalized_yaml['flat_groups'])
            flat_hosts_group.extend(normalized_yaml['flat_hosts'])
        return transpile_to_inventory(flat_vars_group=flat_vars_group, flat_hosts_group=flat_hosts_group, flat_groups_group=flat_groups_group), out_files

    @staticmethod
    def _load_from_toml(toml_files: list[Path]) -> tuple['Inventory', list[Path]]:
        raise ValueError('toml inventory is not currently supported')

    @staticmethod
    def _load_from_json(json_files: list[Path]) -> tuple['Inventory', list[Path]]:
        raise ValueError('json inventory is not currently supported')

    @staticmethod
    def load(files: list[Path] = list()) -> 'Inventory':
        logger = colorlog.getLogger()
        if not isinstance(files, list):
            files = [files]
        if len(files) == 0:
            logger.info("no files provided to load from. Creating new inventory object. Hope you meant to do that")
            return Inventory()
        full_file_list: list[Path] = []
        while len(files) > 0:
            file = files.pop(0)
            if not file.is_dir():
                full_file_list.append(file)
                continue
            logger.debug(f'globbing all items under directory "{file.absolute()}"')
            # glob everything in the directory and toss it back into ini_files
            [files.append(item) for item in file.glob('**/*') if item not in files]
        files = full_file_list
        inventories: list['Inventory'] = []
        parsers = [
            Inventory._load_from_ini,
            # Keep _load_from_yaml last as it will "load" anything without complaints
            Inventory._load_from_yaml
        ]
        for parser in parsers:
            _, files = parser(files)
            inventories.append(_)
        inventory = Inventory()
        inventory.merge(*inventories)
        return inventory
