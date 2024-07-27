from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import colorlog
# Currently this is breaking due to circular dependency.
# We don't _need_ to include this, we just lose
# out on type descriptions if we dont have it
# from modules.inventory.group import Group

from modules import utils

class InvalidHostMatch(Exception):
    def __init__(self, host1: str, host2: str):
        super().__init__(f'Host {host1} and {host2} do not match')

class Host:
    name: str
    groups: dict[str, 'Group'] = dict()
    vars: dict[str, Any] = dict()

    def __init__(self, name: str, vars: dict[str, Any] = dict(), groups: list['Group'] = list()):
        self.name = name
        self.groups = dict()
        [self.add_group(group) for group in groups]
        self.vars = {key: value for key, value in vars.items()}

    def merge(self, *in_hosts: Self):
        logger = colorlog.getLogger()
        for in_host in in_hosts:
            in_host: Self
            if in_host == self:
                # nothing to do here, already merged
                continue
            logger.debug(f"Merging {in_host} with us ({self})")
            if not self.is_same(in_host):
                logger.warning(f"Non matching hostnames {in_host.name} and {self.name}!")
                raise InvalidHostMatch(self.name, in_host.name)
            self.vars = utils.dict_deep_merge(self.vars, in_host.vars, utils.MergePolicy.ACCEPT_RIGHT)
            for key, value in in_host.vars.items():
                if key in self.vars:
                    logger.info(f"Merged Host Vars Key {key} is going to overwrite what we had for this key!")
                self.vars[key] = value

    def add_var(self, key: str, value: Any):
        if key in self.vars:
            colorlog.getLogger().info(f"Replacing variable: {key} in host {self.name}")
        self.vars[key] = value

    def remove_var(self, key: str) -> Any|None:
        if key not in self.vars:
            return
        colorlog.getLogger().debug(f"Removing variable: {key} from host {self.name}")
        return self.vars.pop(key)

    def get_var(self, key: str) -> Any:
        return self.vars.get(key)

    def is_same(self, comp_host: Self) -> bool:
        return self.name == comp_host.name

    def get_groups(self) -> list['Group']:
        return [group for group in self.groups.values()]

    def get_group(self, group_name: str) -> 'Group'|None:
        return self.groups.get(group_name)

    def add_group(self, group: 'Group', _add_self_to_group: bool = True):
        if self.name not in group.hosts and _add_self_to_group:
            group.add_host(self, _add_self_to_host = False)
        if group.name in self.groups:
            self.groups[group.name].merge(group)
        else:
            self.groups[group.name] = group

    def remove_group(self, group_name: str, _remove_self_from_group: bool = True) -> 'Group'|None:
        if group_name not in self.groups:
            return
        group = self.groups[group_name]
        if _remove_self_from_group:
            group.remove_host(self.name, _remove_self_from_host = False)
        del self.groups[group_name]
        return group

    def save(self, save_dir: Path):
        save_host_file = save_dir / 'hosts' / f'{self.name}.yaml'
        save_host_var_file = save_dir / 'vars' / 'hosts' / f'{self.name}.yaml'
        with open(save_host_file, 'w') as _out_file:
            # Test this eventually
            pass

    def as_dict(self) -> dict:
        return {
            'name': self.name,
            'vars': {key: value for key, value in self.vars.items()}
        }

    def __eq__(self, value: object) -> bool:
        return isinstance(value, Host) and self.is_same(value) and self.vars == value.vars

    def __repr__(self) -> str:
        return f'<Host(name="{self.name}", vars={self.vars})'

    def __str__(self) -> str:
        return f'Host: {self.name}'


class HostConnection:
    host: Host
    pass
