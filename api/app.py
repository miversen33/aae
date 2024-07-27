#!/usr/bin/env python3

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from valkey import Valkey
import uvicorn
import colorlog
from fastapi import FastAPI, HTTPException, APIRouter
import dotenv

from modules.settings import Settings
from modules.inventory import Inventory
from modules.inventory.host import Host as InvHost
from models.inventory import Host, HostShort, HostIn, Group, GroupShort

STUPID_LOG_LEVEL_MAPPING_TABLE_BECAUSE_PYTHON_DOESNT_HAVE_ONE = {
    "debug"    : 0,
    "info"     : 10,
    "warn"     : 20,
    "warning"  : 20,
    "error"    : 30,
    "critical" : 40
}

api_version = 'v1'
logger = colorlog.getLogger()
settings: Settings
valkey_connection: Valkey

def setup_logging(log_level: str):
    global logger
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        fmt='%(log_color)s[%(asctime)s] %(levelname)s:%(reset)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        reset = True,
    ))
    logger.addHandler(handler)
    logger.setLevel(STUPID_LOG_LEVEL_MAPPING_TABLE_BECAUSE_PYTHON_DOESNT_HAVE_ONE[log_level])

def setup_valkey():
    global valkey_connection
    logger.debug("checking if we should connect to Valkey")
    if not settings.has_valkey():
        return
    if settings.valkey_socket:
        logger.info(f'setting up connection to valkey over socket "{settings.valkey_socket}"')
        valkey_connection = Valkey(unix_socket_path=settings.valkey_socket)
    elif settings.valkey_host and settings.valkey_port:
        logger.info(f"setting up connection to valkey over {settings.valkey_host}:{settings.valkey_port}")
        valkey_connection = Valkey(host = settings.valkey_host, port = settings.valkey_port)

settings = Settings()
def make_url(url: str) -> str:
    return f'{settings.web_root}/api/{api_version}{url}'


def setup():
    setup_logging(settings.log_level)
    if not settings.load():
        print("Unable to load settings! Please see logs above", file=sys.stderr)
        sys.exit(1)
    setup_valkey()
    logger.info(f"Accessible via {settings.web_url}")

def shutdown():
    pass

@asynccontextmanager
async def lifespan(_: FastAPI):
    setup()
    yield
    shutdown()

server: str = settings.web_url
router = APIRouter(redirect_slashes=False)
app = FastAPI(
    lifespan=lifespan,
    root_path=f'{settings.web_root}',
    openapi_url=f'{settings.web_root}/openapi.json',
    servers=[{'url': settings.web_url, 'description': 'Host'}]
)


@router.get("/")
async def index():
    return "Hello World!"

@router.get('/inventory')
async def get_inventory():
    return Inventory.load([settings.inventory_dir]).as_dict()

@router.get('/inventory/hosts')
async def get_hosts(filter: str = "all") -> list[HostShort]:
    inventory = Inventory.load([settings.inventory_dir])
    hosts = [
        HostShort.generate_from_inventory_host(
            host,
            lambda name: make_url(f"/inventory/hosts/{name}")
        )
        for host in inventory.get_hosts()
    ]
    return hosts

@router.post('/inventory/hosts')
async def add_host(raw_host: HostIn) -> HostShort:
    inventory = Inventory.load([settings.inventory_dir])
    inventory.add_host(raw_host.hostname, *raw_host.groups)
    [inventory.add_host_var(raw_host.hostname, key, value) for key, value in raw_host.variables.items()]
    other_vars = ['user', 'password', 'private_key', 'ssh_port']
    # TODO: We should probably be using the ansible secret vault for any secrets
    for other_var in other_vars:
        # TODO: is there a better way to do this?
        if value := raw_host.__getattribute__(other_var):
            inventory.add_host_var(raw_host.hostname, other_var, value)
    await inventory.save(settings.inventory_dir)
    return HostShort(name = raw_host.hostname, link = make_url(f'/inventory/hosts/{raw_host.hostname}'))

@router.delete('/inventory/hosts/{hostname}')
async def remove_host(host_name: str) -> dict[str, bool]:
    inventory = Inventory.load([settings.inventory_dir])
    inventory.remove_host(host_name)
    await inventory.save(settings.inventory_dir)
    return {'success': True}

@router.get('/inventory/hosts/{hostname}')
async def get_host(hostname: str) -> Host:
    inventory = Inventory.load([settings.inventory_dir])
    host = inventory.get_host(hostname)
    if not host:
        raise HTTPException(status_code=404, detail = f"Unable to locate host associated with \"{hostname}\"")
    return Host.generate_from_inventory_host(
        host,
        host_url_crafter = lambda s: make_url(f"/inventory/hosts/{s}"),
        group_url_crafter = lambda s: make_url(f"/inventory/groups/{s}")
    )

@router.get('/inventory/groups')
async def get_groups() -> list[GroupShort]:
    inventory = Inventory.load([settings.inventory_dir])
    groups: list[GroupShort] = [
        GroupShort.generate_from_inventory_group(
            group,
            lambda name: make_url(f"/inventory/groups/{name}"))
            for group in inventory.get_groups()
        ]
    return groups

@router.get('/inventory/groups/{groupname}')
async def get_group(groupname: str) -> Group:
    inventory = Inventory.load([settings.inventory_dir])
    raw_group = inventory.get_group(groupname)
    if not raw_group:
        raise HTTPException(status_code=404, detail = f"Unable to locate group associated with \"{groupname}\"")
    group = Group.generate_from_inventory_group(
    raw_group,
        host_url_crafter = lambda s: make_url(f'/inventory/hosts/{s}'),
        group_url_crafter = lambda s: make_url(f'/inventory/groups/{s}')
    )
    return group

def main():
    if settings._is_dev:
        logger.warning("Starting AAE in dev mode!")
    else:
        logger.warning("Starting AAE")
    config = uvicorn.Config(
        "app:app",
        port = settings.web_port,
        log_level = settings.log_level or 'info',
        host = "0.0.0.0",
        reload = settings._is_dev
    )
    server = uvicorn.Server(config)
    server.run()

app.include_router(router, prefix = f"/api/{api_version}")

if __name__ == "__main__":
    main()

