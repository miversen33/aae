from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRouter
from contextlib import asynccontextmanager
import dotenv
import os

import logging
from logging import Logger
from modules.host import Hosts
from modules.pubkey import Pubkey, VALID_ACCESS_METHODS

VERSION="0.0.1"

logger: Logger
PUBKEYS = {}
RESOURCES = Path() / "resources"
DOMAIN: str = ""
ROOT_PATH: str = "/"
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
    global ANSIBLE_INVENTORY_LOCATION, ROOT_PATH, DOMAIN
    log_level = os.environ.get("LOG_LEVEL")
    if not log_level or log_level.isspace() or len(log_level) == 0:
        # Annoying that I have to do this...
        log_level = "WARNING"
    create_logger(log_level)
    DOMAIN = os.environ.get("DOMAIN", "")
    if len(DOMAIN) > 0:
        logger.info(f"Setting Domain to \"{DOMAIN}\"")
    _raw_ansible_inventory_location = os.environ.get("ANSIBLE_INVENTORY_LOCATION")
    ROOT_PATH = os.environ.get("ROOT_PATH", "")
    if ROOT_PATH.endswith('/'):
        ROOT_PATH = ROOT_PATH[:-1]
    logger.info(f"Setting Root Path to \"{ROOT_PATH}\"")
    logger.debug("Checking Ansible Inventory Location")
    if not _raw_ansible_inventory_location or len(_raw_ansible_inventory_location) == 0:
        raise ValueError("Ansible Location not defined! Please set the environment variable ANSIBLE_INVENTORY_LOCATION")
    ANSIBLE_INVENTORY_LOCATION=Path(_raw_ansible_inventory_location)
    if ANSIBLE_INVENTORY_LOCATION.exists() and ANSIBLE_INVENTORY_LOCATION.is_file():
        raise ValueError(f"Ansible location {_raw_ansible_inventory_location} is not a directory!")
    try:
        Path(ANSIBLE_INVENTORY_LOCATION / "hosts.yaml").touch()
    except PermissionError:
        raise ValueError(f"Unable to write to hosts file in ansible location: {_raw_ansible_inventory_location}!")
    load_pubkey_locations()

def shutdown():
    # If you need to do any stuff after the application is dead, do that here
    pass

@asynccontextmanager
async def lifespan(_: FastAPI):
    # We have nothing to do beforehand
    yield
    shutdown()

dotenv.load_dotenv()
setup()
router = APIRouter()
app: FastAPI

def get_environments() -> List[str]:
    return [env for env in PUBKEYS.keys()]

def get_inventory() -> Hosts:
    return Hosts.load(ANSIBLE_INVENTORY_LOCATION)


def generate_link(request: Request, path: str) -> str:
    return f'{request.url.scheme}://{DOMAIN if len(DOMAIN) > 0 else request.url.netloc}{ROOT_PATH}/{path}'

@router.get("/")
async def root():
    # TODO: Create webui enroller
    return ""

@router.get("/ping", response_class=PlainTextResponse)
async def ping():
    return "pong"


@router.get("/enroll", response_class=PlainTextResponse)
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

@router.get("/inventory")
async def inventory(format: str = "json"):
    inventory = get_inventory()
    return Response(content = inventory.serialize(format), media_type='text/plain' if format != 'json' else 'application/json')

@router.get("/do_enroll")
async def do_enroll(hostname: str = "", user: str = 'root', os_type: str = "", environment: str = "", applications: str = ""):
    app_list: List[str] = applications.split(',') if len(applications) > 0 else []
    inventory=get_inventory()
    if hostname in inventory:
        # Nothing to do as the host is already enrolled
        return f"{hostname} is already enrolled"
    groups={'all', os_type, environment}
    for app in app_list:
        groups.add(app)
    logger.debug(f"Adding {hostname} to the following groups. {os_type}, {environment}, {', '.join(app_list)}")
    
    inventory.add_host(hostname, list(groups), user=user)
    inventory.save_to_disk(ANSIBLE_INVENTORY_LOCATION / 'hosts.yaml')

    next_merge=""
    next_update_file = Path(ANSIBLE_INVENTORY_LOCATION / ".nextupdate")
    if next_update_file.exists():
        with open(next_update_file, 'r') as _in_file:
            next_merge = _in_file.read()
    else:
        next_merge = "Unknown"
    return { 'response' : f"Successfully added \"{hostname}\" to ansible inventory. Next automated inventory merge is \"{next_merge}\"" }

@router.get("/pubkey")
async def get_public_keys():
    keys = dict()
    for key, value in PUBKEYS.items():
        keys[key] = str(value)
    return keys

@router.get("/pubkey/{environment}", response_class=PlainTextResponse)
async def get_public_key(environment):
    global PUBKEYS
    if not environment or not PUBKEYS.get(environment.upper()):
        available_pubkeys = ",".join(PUBKEYS.keys())
        raise HTTPException(
            status_code = 400,
                detail = f'Environment `{environment}` does not have a pubkey available. Valid Environments are: {available_pubkeys}'
        )
    return str(PUBKEYS.get(environment.upper()))

app = FastAPI(lifespan=lifespan, root_path=ROOT_PATH)
app.include_router(router, prefix=ROOT_PATH)

