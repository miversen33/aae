from __future__ import annotations

import re
from typing import Callable, Any
from pydantic import BaseModel

from modules.inventory.host import Host as InvHost
from modules.inventory.group import Group as InvGroup

FORBIDDEN_VAR_REGEX = re.compile(r'(?:(?:password)|(?:private_key))', re.IGNORECASE)

class HostShort(BaseModel):
    name: str
    link: str

    @staticmethod
    def generate_from_inventory_host(host: InvHost, host_url_crafter: Callable) -> 'HostShort':
        return HostShort(
            name = host.name,
            link = host_url_crafter(host.name)
        )

class GroupShort(BaseModel):
    name: str
    link: str

    @staticmethod
    def generate_from_inventory_group(group: InvGroup, group_url_crafter: Callable) -> 'GroupShort':
        return GroupShort(
            name = group.name,
            link = group_url_crafter(group.name)
        )


class Host(BaseModel):
    name: str
    hostname: str
    link: str
    groups: list[GroupShort]
    variables: dict[str, Any]
    ip_address: str|None = None

    @staticmethod
    def generate_from_inventory_host(host: InvHost, host_url_crafter: Callable, group_url_crafter: Callable) -> 'Host':
        return Host(
            name = host.name,
            hostname = host.name,
            link = host_url_crafter(host.name),
            groups = [GroupShort(name = group.name, link = group_url_crafter(group.name)) for group in host.groups.values()],
            variables= {key: value if not FORBIDDEN_VAR_REGEX.match(key) else "****" for key, value in host.vars.items()}
        )
    # @staticmethod
    # def generate_from_ansible_host(host: AnsibleHost, host_vars: dict, host_url_crafter: Callable, group_url_crafter: Callable) -> Self:
    #     return Host(
    #         name = host.get_name(),
    #         hostname = host.get_name(),
    #         groups = [ GroupShort(name = group.name, link = group_url_crafter(group.name)) for group in host.get_groups() ],
    #         variables = host_vars,
    #         link = host_url_crafter(host.get_name())
    #     )

class Group(BaseModel):
    name: str
    variables: dict[str, Any]
    parent_groups: list[GroupShort] = list()
    children_groups: list[GroupShort] = list()
    children_hosts: list[HostShort] = list()
    link: str

    @staticmethod
    def generate_from_inventory_group(group: InvGroup, host_url_crafter: Callable, group_url_crafter: Callable) -> 'Group':
        return Group(
            name = group.name,
            parent_groups=[GroupShort(name = parent.name, link = group_url_crafter(parent.name)) for parent in group.parents.values()],
            children_groups=[GroupShort(name = child.name, link = group_url_crafter(child.name)) for child in group.children.values()],
            children_hosts=[HostShort(name = child.name, link = host_url_crafter(child.name)) for child in group.hosts.values()],
            link = group_url_crafter(group.name),
            variables={key: value if not FORBIDDEN_VAR_REGEX.match(key) else "****" for key, value in group.vars.items()}
       )
    # @staticmethod
    # def generate_from_ansible_group(group: AnsibleGroup, group_vars: dict, host_url_crafter: Callable, group_url_crafter: Callable) -> Self:
    #     return Group(
    #         name = group.get_name(),
    #         parent_groups = [ GroupShort(name = parent.name, link = group_url_crafter(parent.name)) for parent in group.get_ancestors()],
    #         children_groups = [ GroupShort(name = child.name, link = group_url_crafter(child.name)) for child in group.get_descendants()],
    #         children_hosts = [ HostShort(name = child.name, link = host_url_crafter(child.name)) for child in group.get_hosts()],
    #         variables = group_vars,
    #         link = group_url_crafter(group.get_name())
    #     )


class HostIn(BaseModel):
    hostname: str
    name: str|None = None
    ip_address: str|None = None
    groups: list[str] = []
    variables: dict[str, str|list[str]|dict[str, str]] = dict()
    user: str|None = None
    password: str|None = None
    private_key: str|None = None
    ssh_port: int = 22

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f'''<HostIn(hostname="{self.hostname}", ip_address="{self.ip_address or ''}", groups={self.groups or []}, variables={self.variables or dict()}, user="{self.user or ''}", password="{self.password and '*****' or ''}", private_key="{self.private_key and '*****' or ''}", ssh_port={self.ssh_port})'''

