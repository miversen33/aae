from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set
import yaml
import re

# Annoying ass thing pulled from here: https://github.com/yaml/pyyaml/issues/535#issuecomment-1293636712 because pyyaml 
# insists that fucking anchors are required
class VerboseSafeDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True

class Host():
    """
    Class representation of an individual host in an ansible inventory
    """
    hostname: str
    user: str
    groups: Set[str]
    variables: Dict[str, Any]

    def __init__(self, hostname: str, user: str = "", groups: List[str]|None = None, vars: Dict[str, Any]|None = None):
        self.hostname = hostname
        self.groups = set()
        self.variables = dict()
        self.user = user
        if not groups:
            groups = ["ungrouped"]
        if not vars:
            vars = dict()
        for group in groups:
            self.groups.add(group)
        for key, value in vars.items():
            self.variables[key] = value

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, Host) and __value.hostname == self.hostname or isinstance(__value, str) and __value == self.hostname

    def __str__(self) -> str:
        return f'{self.hostname}({", ".join(self.groups)})'

    def __repr__(self) -> str:
        return f'''<Host(hostname="{self.hostname}", user="{self.user}", groups={self.groups}, vars={self.variables})>'''

    def _serialize_as_ini(self) -> str:
        entry = [self.hostname]
        if self.user:
            self.variables['ansible_user'] = self.user
        for variable_key, variable_value in self.variables.items():
            entry.append(f'{variable_key}={variable_value}')
        return " ".join(entry)

    def has_group(self, group_name: str) -> bool:
        return group_name == 'all' or group_name in self.groups

    def add_group(self, group_name: str):
        if group_name not in ['all', 'ungrouped'] and 'ungrouped' in self.groups:
            # Ensure a host is not left ungrouped if its grouped
            self.groups.remove('ungrouped')
        self.groups.add(group_name)

    def get_groups(self) -> List[str]:
        return list(self.groups)

    def __getstate__(self) -> object:
        return { self.hostname: self.variables } if len(self.variables) > 0 else { self.hostname: [] }

    def remove_group(self, group_name: str):
        self.groups.remove(group_name)

    def set_variable(self, var_name: str, value: Any):
        self.variables[var_name] = value

    def remove_variable(self, var_name: str):
        if self.variables.get(var_name):
            del(self.variables[var_name])

class Hosts():
    """
    Your ansible inventory
    """
    
    hosts: List[Host]

    @staticmethod
    def _load_from_ini(hostfile: Path) -> Hosts:
        """
        Because ansible bastardizes ini files, we are going to have to write our own parser...
        """
        hosts: Hosts = Hosts()
        line_is_section_header_regex = re.compile(r'^\[(?P<section>[^\[\]]+)\]')
        line_is_host_regex = re.compile(r'^\s*(?P<host>[a-zA-Z0-9.-]+)')
        with open(hostfile, 'r') as _in_file:
            current_group: str = "ungrouped"
            for line in _in_file.readlines():
                line_is_header = line_is_section_header_regex.match(line)
                line_is_host = line_is_host_regex.match(line)
                if line_is_header:
                    # We have a header
                    current_group = line_is_header.groupdict().get('section')
                if line_is_host:
                    hostname = line_is_host.groupdict().get('host')
                    if not hosts.get_host(hostname):
                        hosts.add_host(hostname)
                    host: Host = hosts.get_host(hostname)
                    host.add_group(current_group)
                    host_variables = line.split(" ")
                    if len(host_variables) > 1:
                        for variable in host_variables[1:]:
                            key, value = variable.split("=")
                            host.set_variable(key, value.rstrip())
        return hosts

    @staticmethod
    def _load_from_yaml(hostfile: Path) -> Hosts:
        hosts: Hosts = Hosts()
        config = dict()
        with open(hostfile, 'r') as _in_file:
            config = yaml.safe_load(_in_file)
            if not config:
                return hosts
            for group, raw_hosts in config.items():
                for hostname, host_details in raw_hosts.get("hosts").items():
                    if not hosts.get_host(hostname):
                        hosts.add_host(hostname)
                    if not host_details:
                        host_details = dict()
                    host: Host = hosts.get_host(hostname)
                    for variable_name, value in host_details.items():
                        host.set_variable(variable_name, value)
                    host.add_group(group)
        return hosts


    @staticmethod
    def _load_from_json(json_file: Path) -> Hosts|None:
        return None

    @staticmethod
    def load(hostfiles: str|List[str]|List[Path]|Path) -> Hosts:
        """
        Will attempt to intelligently load the hostfile based on its extension
        """
        if isinstance(hostfiles, str):
            hostfiles = [Path(hostfiles)]
        if isinstance(hostfiles, list):
            temp_host_files = [Path(hostfile) for hostfile in hostfiles]
            hostfiles = temp_host_files
                
        if isinstance(hostfiles, Path):
            hostfiles = [ hostfiles ]
        hosts = Hosts()
        loaded_hosts: List[Hosts] = list()
        while len(hostfiles) > 0:
            hostfile = Path(hostfiles.pop(0))
            if hostfile.is_dir():
                # For some dumbshit reason I cannot just use glob('*.[yamlin]')...
                for _ in hostfile.glob('*.yaml'):
                    hostfiles.append(_)
                for _ in hostfile.glob('*.yml'):
                    hostfiles.append(_)
                for _ in hostfile.glob('*.ini'):
                    hostfiles.append(_)
                continue
            if hostfile.suffix in [ '.yml', '.yaml' ]:
                loaded_hosts.append(Hosts._load_from_yaml(hostfile))
            elif hostfile.suffix in [ '.ini' ]:
                loaded_hosts.append(Hosts._load_from_ini(hostfile))
            else:
                # Discarding this item
                pass
        hosts.merge_hosts(loaded_hosts)
        return hosts

    def __init__(self, hosts: List[Host]|None = None) -> None:
        if not hosts:
            hosts = list()
        self.hosts = hosts

    def add_host(self, host: Host|str, groups: List[str]|None = None, user: str = "root"):
        if not groups:
            groups = list()
        if host not in self.hosts:
            if isinstance(host, str):
                host = Host(hostname=host)
            host.user = user
            [host.add_group(group) for group in groups]
            self.hosts.append(host)

    def remove_host(self, hostname: str) -> Host|None:
        if hostname not in self.hosts:
            return
        host = self.hosts[self.hosts.index(hostname)]
        self.hosts.remove(host)
        return host

    def has_host(self, hostname: str) -> bool:
        return hostname in self.hosts

    def get_host(self, hostname: str) -> Host|None:
        if hostname not in self.hosts:
            return
        return self.hosts[self.hosts.index(hostname)]

    def get_hosts(self, group_name: str = "all") -> List[Host]:
        return [host for host in filter(lambda host: group_name in host.groups, self.hosts)]

    def get_hostnames(self) -> List[str]:
        return [host.hostname for host in self.hosts]

    def get_groups(self) -> List[str]:
        groups = set()
        for host in self.hosts:
            for group in host.groups:
                groups.add(group)
        return list(groups)

    def filter(self, groups: List[str]|None = None) -> Hosts:
        if not groups:
            return Hosts()
        hosts: List[Host] = list()
        [hosts.extend(self.get_hosts(group)) for group in groups]
        return Hosts(hosts)

    def merge_hosts(self, hosts: List[Hosts]|Hosts):
        if isinstance(hosts, Hosts):
            hosts = [hosts]
        for host_holder in hosts:
            for host in host_holder.hosts:
                if host not in self.hosts:
                    self.add_host(host)

    def save_to_disk(self, save_file: Path):
        with open(save_file, 'w') as _out_file:
            _out_file.write(self.serialize(save_file.suffix.split('.')[1]))

    def serialize(self, format: str) -> str:
        VALID_FORMATS = [ "ini", "json", "yaml" ]
        format = format.lower()
        if format == 'ini':
            return self._serialize_as_ini()
        elif format == 'json':
            return self._serialize_as_json()
        elif format in ["yaml", 'yml']:
            return self._serialize_as_yaml()
        else:
            raise ValueError(f"Format \"{format}\" is not a valid serialization format. Valid formats are {VALID_FORMATS}")

    def _serialize_as_ini(self) -> str:
        """
        Returns a string that should be valid ansible inventory ini format
        """
        config_as_list = []
        for ungrouped_host in self.get_hosts("ungrouped"):
            config_as_list.append(ungrouped_host._serialize_as_ini())
        
        for group_name in self.get_groups():
            if group_name == 'ungrouped':
                # Already been processed
                continue
            config_as_list.append("")
            config_as_list.append(f'[{group_name}]')
            for host in self.get_hosts(group_name):
                config_as_list.append(host._serialize_as_ini())
        return "\n".join(config_as_list)

    def _serialize_as_yaml(self) -> str:
        """
        Takes in the output for `merge_host_groups`

        Returns a string that should be valid ansible inventory yaml format
        """
        groups = dict()
        for group_name in self.get_groups():
            groups[group_name] = { 'hosts': dict() }
            for host in self.get_hosts(group_name):
                host_entry = host.variables if host.variables else dict()
                if host.user and not host.variables.get('ansible_user'):
                    host_entry['ansible_user'] = host.user
                if len(host_entry) == 0:
                    host_entry = None
                groups[group_name]['hosts'][host.hostname] = host_entry
            # Some nastyness because None is how you tag a dictionary as an empty dict in yaml but ansible doesn't use "null" to indicate this
            # in their inventory scripts
        return yaml.dump(groups, Dumper=VerboseSafeDumper).replace('null', '')

    def _serialize_as_json(self) -> str:
        hosts = dict(all=list())
        all_hosts = set()
        for group in self.get_groups():
            if not hosts.get(group):
                hosts[group] = list()
            for host in self.get_hosts(group):
                serial_host={
                    host.hostname: {
                        'groups': host.get_groups(),
                        'variables': host.variables
                    }
                }
                if group != 'all':
                    hosts[group].append(serial_host)
                if host.hostname not in all_hosts:
                    hosts['all'].append(serial_host)
                    all_hosts.add(host.hostname)
        return json.dumps(hosts)

    def __str__(self) -> str:
        return f"Hosts: {self.hosts}"

    def __repr__(self) -> str:
        return f"""<Hosts(hosts={self.hosts})"""

    def __contains__(self, item) -> bool:
        return item in self.hosts

