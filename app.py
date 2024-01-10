from pathlib import Path
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
import dotenv
import yaml
import os

import logging
from logging import Logger

from modules.pubkey import Pubkey, VALID_ACCESS_METHODS

VERSION="0.0.1"

logger: Logger
PUBKEYS = {}
RESOURCES = Path() / "resources"
PUBLIC_PATH: str = ""
ANSIBLE_INVENTORY_LOCATION: Path = Path()

class NoPubkeysException(Exception):
    def __init__(self):
        super().__init__("No pubkeys were loaded!")

def create_logger(level: str = "WARNING"):
    global logger
    logger = logging.getLogger("app")
    stdout_handler = logging.StreamHandler()
    stdout_formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    stdout_handler.setFormatter(stdout_formatter)
    logger.addHandler(stdout_handler)
    logger.setLevel(level.upper())

def load_pubkey_locations():
    global PUBKEYS
    logger.info("Loading Pubkeys")
    env_names = os.environ.get("PUBKEY_ENVS")
    pubkey_store = os.environ.get("PUBKEY_STORE", "")
    if env_names is None:
        logger.error('Unable to locate "PUBKEY_ENVS" environment variable!')
        raise NoPubkeysException()
    if pubkey_store.isspace() or len(pubkey_store) == 0:
        # TODO: Add support for redis pubkey store
        logger.warning(f'''Environment variable "PUBKEY_STORE" not set, defaulting to file. Valid PUBKEY_STORE values are {", ".join([f'"{am}"' for am in VALID_ACCESS_METHODS])}''')
        pubkey_store = "FILE"
    env_names = [env.lstrip().rstrip().upper() for env in env_names.split(",")]
    for env_name in env_names:
        env = os.environ.get(f'PUBKEY_{env_name}')
        if not env:
            continue
        logger.debug(f'Loading Pubkey for "{env_name}"')
        PUBKEYS[env_name] = Pubkey(pubkey_location=env, pubkey_access_method=pubkey_store)
    if len(PUBKEYS) == 0:
        raise NoPubkeysException()

def setup():
    global ANSIBLE_INVENTORY_LOCATION, PUBLIC_PATH
    log_level = os.environ.get("LOG_LEVEL")
    if not log_level or log_level.isspace() or len(log_level) == 0:
        # Annoying that I have to do this...
        log_level = "WARNING"
    create_logger(log_level)
    PUBLIC_PATH = os.environ.get("PUBLIC_PATH", "")
    if PUBLIC_PATH.endswith("/"):
        PUBLIC_PATH = PUBLIC_PATH[:-1]
    if len(PUBLIC_PATH) > 0:
        logger.info("Setting Public Path to \"\"")
    _raw_ansible_inventory_location = os.environ.get("ANSIBLE_INVENTORY_LOCATION")
    logger.debug("Checking Ansible Inventory Location")
    if not _raw_ansible_inventory_location or len(_raw_ansible_inventory_location) == 0:
        raise ValueError("Ansible Location not defined! Please set the environment variable ANSIBLE_INVENTORY_LOCATION")
    ANSIBLE_INVENTORY_LOCATION=Path(_raw_ansible_inventory_location)
    if ANSIBLE_INVENTORY_LOCATION.exists() and not ANSIBLE_INVENTORY_LOCATION.is_file():
        raise ValueError(f"Ansible location {_raw_ansible_inventory_location} is not a file!")
    try:
        ANSIBLE_INVENTORY_LOCATION.touch()
    except PermissionError:
        raise ValueError(f"Unable to write to ansible location: {_raw_ansible_inventory_location}!")
    load_pubkey_locations()

def shutdown():
    # If you need to do any stuff after the application is dead, do that here
    pass

@asynccontextmanager
async def lifespan(_: FastAPI):
    # We have nothing to do beforehand
    setup()
    yield
    shutdown()

dotenv.load_dotenv()
app = FastAPI(lifespan=lifespan)

def get_environments() -> List[str]:
    return [env for env in PUBKEYS.keys()]

def get_inventory() -> Dict[str, List[str]]:
    loader = DataLoader()
    inventory = InventoryManager(loader = loader, sources = [ str(ANSIBLE_INVENTORY_LOCATION.absolute())])
    return inventory.get_groups_dict()

def generate_link(request: Request, path: str) -> str:
    path_head=PUBLIC_PATH if len(PUBLIC_PATH) > 0 else f'{request.url.scheme}://{request.url.netloc}'
    return f"{path_head}/{path}"

@app.get("/")
async def root():
    # TODO: Create webui enroller
    return "pong"

@app.get("/enroll", response_class=PlainTextResponse)
async def enroll(request: Request):
    enroll_script = ""
    with open(RESOURCES / "enroll.sh", "r") as _in_file:
        enroll_script = _in_file.read()
    enroll_link=generate_link(request, "do_enroll")
    enroll_script=enroll_script.replace("ENROLL_LINK=", f"ENROLL_LINK={enroll_link}")
    envs = [f'"{env}"' for env in get_environments()]
    enroll_script=enroll_script.replace("ENVIRONMENTS=", f'ENVIRONMENTS=({" ".join(envs)})')
    pubkey_link=generate_link(request, "pubkey")
    enroll_script=enroll_script.replace("SSH_PUBKEY_LINK=", f'SSH_PUBKEY_LINK={pubkey_link}')
    return enroll_script

@app.get("/inventory")
async def inventory():
    return get_inventory()

@app.get("/do_enroll")
async def do_enroll(hostname: str = "", os_type: str = "", environment: str = "", applications: str = ""):
    app_list: List[str] = applications.split(',')
    inventory=get_inventory()
    all_inventory=inventory.get("all", list())
    if hostname in all_inventory:
        # Nothing to do as the host is already enrolled
        return f"{hostname} is already enrolled"
    if not inventory.get("all"):
        inventory['all'] = []
    inventory["all"].append(hostname)
    if not inventory.get(os_type):
        inventory[os_type] = []
    if hostname not in inventory[os_type]:
        inventory[os_type].append(hostname)
    if not inventory.get(environment):
        inventory[environment] = []
    if hostname not in inventory[environment]:
        inventory[environment].append(hostname)
    for app in app_list:
        if not inventory.get(app):
            inventory[app] = []
        if hostname not in inventory[app]:
            inventory[app].append(hostname)
    logger.debug(f"Adding {hostname} to the following groups. {os_type}, {environment}, {', '.join(app_list)}")
    with open(ANSIBLE_INVENTORY_LOCATION, 'w') as _out_file:
        yaml.dump(inventory, _out_file)
    next_merge="Never"
    return f"Successfully added \"{hostname}\" to ansible inventory. Next automated inventory merge is \"{next_merge}\""

@app.get("/pubkey")
async def get_public_keys():
    keys = dict()
    for key, value in PUBKEYS.items():
        keys[key] = str(value)
    return keys

@app.get("/pubkey/{environment}", response_class=PlainTextResponse)
async def get_public_key(environment):
    global PUBKEYS
    if not environment or not PUBKEYS.get(environment.upper()):
        available_pubkeys = ",".join(PUBKEYS.keys())
        raise HTTPException(
            status_code = 400,
                detail = f'Environment `{environment}` does not have a pubkey available. Valid Environments are: {available_pubkeys}'
        )
    return str(PUBKEYS.get(environment.upper()))


