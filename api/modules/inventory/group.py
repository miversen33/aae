from typing import TYPE_CHECKING
from typing import Any, Self

import colorlog

from modules.inventory.host import Host
from modules import utils

class InvalidGroupMatch(Exception):
    def __init__(self, group1: str, group2: str) -> None:
        super().__init__(f'Group {group1} and {group2} do not match')

class Group:
    name: str
    parents: dict[str, Self]
    children: dict[str, Self]
    vars: dict[str, Any]
    hosts: dict[str, Host]

    def __init__(self, name: str, parents: list[Self] = list(), children: list[Self] = list(), vars: dict[str, Any] = dict(), hosts: list[Host] = list()):
        self.name = name
        self.parents = dict()
        self.children = dict()
        self.hosts = dict()
        self.vars = vars or dict()
        [self.add_parent(parent) for parent in parents]
        [self.add_child(child) for child in children]
        [self.add_host(host) for host in hosts]

    def merge(self, *in_groups: Self):
        logger = colorlog.getLogger()
        for in_group in in_groups:
            in_group: Self
            if in_group == self:
                # nothing to do here, already merged
                continue
            logger.debug(f"Merging {in_group} with us ({self})")
            if not self.is_same(in_group):
                logger.warning(f"Non matching groupnames {in_group.name} and {self.name}!")
                raise InvalidGroupMatch(in_group.name, self.name)
            for parent_name, parent in in_group.parents.items():
                if parent_name in self.parents:
                    self.parents[parent_name].merge(parent)
                else:
                    self.parents[parent_name] = parent
            for child_name, child in in_group.children.items():
                if child_name in self.children:
                    self.children[child_name].merge(child)
                else:
                    self.children[child_name] = child
            for host_name, host in in_group.hosts.items():
                if host_name in self.hosts:
                    self.hosts[host_name].merge(host)
                else:
                    self.hosts[host_name] = host
            self.vars = utils.dict_deep_merge(self.vars, in_group.vars, utils.MergePolicy.ACCEPT_RIGHT)

    def add_var(self, key: str, value: Any):
        if key in self.vars:
            colorlog.getLogger().info(f"Replacing variable: {key} in group {self}")
        colorlog.getLogger().debug(f"Adding {key} to group {self} vars")
        self.vars[key] = value

    def remove_var(self, key: str) -> Any|None:
        if key not in self.vars:
            return
        colorlog.getLogger().debug(f"Removing variable: {key} from group {self}")
        return self.vars.pop(key)

    def get_var(self, key: str) -> Any:
        return self.vars.get(key)

    def get_parents(self) -> list[Self]:
        return [parent for parent in self.parents.values()]

    def get_parent(self, parent_name: str) -> Self|None:
        return self.parents.get(parent_name)

    def add_parent(self, parent: Self):
        if self.name not in parent.children:
            parent.children[self.name] = self
        if parent.name in self.parents:
            colorlog.getLogger().info(f"Merging parent: {parent.name} with our matching reference of it in {self}")
            self.parents[parent.name].merge(parent)
            return
        colorlog.getLogger().debug(f"Adding parent: {parent.name} to group {self} parents")
        self.parents[parent.name] = parent

    def remove_parent(self, parent_name: str) -> Self|None:
        if parent_name not in self.parents:
            return
        colorlog.getLogger().info(f"Removing parent: {parent_name} from group {self} parents")
        parent = self.parents.pop(parent_name)
        if self.name in parent.children:
            del parent.children[self.name]
        return parent

    def get_children(self) -> list[Self]:
        return [child for child in self.children.values()]

    def get_child(self, child_name: str) -> Self|None:
        return self.children.get(child_name)

    def add_child(self, child: Self):
        if self.name not in child.parents:
            child.parents[self.name] = self
        if child.name in self.children:
            colorlog.getLogger().info(f"Merging child: {child.name} with our matching reference of it in {self}")
            self.children[child.name].merge(child)
            return
        colorlog.getLogger().debug(f"Adding child: {child.name} to group {self} children")
        self.children[child.name] = child

    def remove_child(self, child_name: str) -> Self|None:
        if child_name not in self.children:
            return
        child = self.children[child_name]
        if self.name in child.parents:
            del child.parents[self.name]
        colorlog.getLogger().info(f"Removing child: {child_name} from group {self} children")
        return self.children.pop(child_name)

    def add_host(self, host: Host, _add_self_to_host: bool = True):
        if host.name in self.hosts:
            colorlog.getLogger().info(f"Merging {host} with our matching reference of it in {self}")
            self.hosts[host.name].merge(host)
        else:
            colorlog.getLogger().debug(f"Adding {host} to hosts in {self.name}")
            self.hosts[host.name] = host
        if _add_self_to_host:
            host.add_group(self, _add_self_to_group = False)


    def remove_host(self, host_name: str, _remove_self_from_host: bool = True) -> Host|None:
        if host_name not in self.hosts:
            return
        colorlog.getLogger().info(f"Removing {host_name} from hosts in {self}")
        host = self.hosts[host_name]
        if _remove_self_from_host:
            host.remove_group(self.name, _remove_self_from_group = False)
        del self.hosts[host_name]
        return host

    def get_host(self, host_name: str) -> Host|None:
        return self.hosts.get(host_name, None)

    def get_hosts(self) -> list[Host]:
        return [host for host in self.hosts.values()]

    def as_dict(self, ignore_hosts: bool = False, ignore_parents: bool = False, ignore_children: bool = False) -> dict:
        self_as_dict = {
            'name': self.name,
            'vars': {key: value for key, value in self.vars.items()},
            'hosts': {host.name:None for host in self.hosts.values()},
            'children': {child.name: None for child in self.children.values()}
        }
        return self_as_dict

    def is_same(self, comp_group: Self) -> bool:
        return self.name == comp_group.name

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Group):
            return False
        value: Self
        self_parents = sorted(list(self.parents.keys()))
        their_parents = sorted(list(value.parents.keys()))
        self_children = sorted(list(self.children.keys()))
        their_children= sorted(list(value.children.keys()))
        self_hosts = sorted(list(self.hosts.keys()))
        their_hosts = sorted(list(value.hosts.keys()))

        return self.is_same(value) and self_parents == their_parents and self_children == their_children and self_hosts == their_hosts and self.vars == value.vars

    def __repr__(self) -> str:
        return f'<Group(name="{self.name}", parents={self.parents}, children={self.children},vars={self.vars}, hosts={self.hosts})'

    def __str__(self) -> str:
        return f"Group: {self.name}"
