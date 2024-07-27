import os
from pathlib import Path

import colorlog

ENV_ANSIBLE_DIR = 'ANSIBLE_DIR'
ENV_ANSIBLE_SSH_KEYS_DIR = 'ANSIBLE_SSH_KEYS_DIR'
ENV_ANSIBLE_WEB_PORT = 'ANSIBLE_WEB_PORT'
ENV_ANSIBLE_WEB_ROOT = 'ANSIBLE_WEB_ROOT'
ENV_ANSIBLE_WEB_URL = 'ANSIBLE_WEB_URL'
ENV_ANSIBLE_IS_DEV = 'ANSIBLE_DEV'
ENV_ANSIBLE_LOG_LEVEL = 'ANSIBLE_LOG_LEVEL'
ENV_ANSIBLE_VALKEY_PORT = 'ANSIBLE_VALKEY_PORT'
ENV_ANSIBLE_VALKEY_HOST = 'ANSIBLE_VALKEY_HOST'
ENV_ANSIBLE_VALKEY_SOCKET = 'ANSIBLE_VALKEY_SOCKET'

class Settings:
    playbooks_dir: Path
    ssh_keys_dir: Path
    inventory_dir: Path
    web_url: str

    ansible_dir: Path = Path("/opt/ansible")
    web_port: int = 8000
    web_root: str = "/"
    _is_dev: bool = False
    log_level: str = "warning"
    valkey_port: int|None = None
    valkey_host: str|None = None
    valkey_socket: Path|None = None

    def __init__(self,
                ansible_dir: Path|None = None,
                ssh_keys_dir: Path|None = None,
                web_port: int|None = None,
                web_root: str|None = None,
                web_url: str|None = None,
                is_dev: bool|None = None,
                log_level: str|None = None,
                valkey_port: int|None = None,
                valkey_host: str|None = None,
                valkey_socket: Path|None = None
            ):
        env = os.environ
        self.ansible_dir = ansible_dir if ansible_dir else Path(env.get(ENV_ANSIBLE_DIR)) if ENV_ANSIBLE_DIR in env else self.ansible_dir
        self.web_port = web_port if web_port else int(env.get(ENV_ANSIBLE_WEB_PORT)) if ENV_ANSIBLE_WEB_PORT in env else self.web_port
        self.web_root = web_root if web_root else str(env.get(ENV_ANSIBLE_WEB_ROOT)) if ENV_ANSIBLE_WEB_ROOT in env else self.web_root
        if self.web_root == '/':
            self.web_root = ''
        self._is_dev = is_dev if is_dev else bool(env.get(ENV_ANSIBLE_IS_DEV)) if ENV_ANSIBLE_IS_DEV in env else self._is_dev
        self.log_level = log_level if log_level else str(env.get(ENV_ANSIBLE_LOG_LEVEL)) if ENV_ANSIBLE_LOG_LEVEL in env else self.log_level
        self.valkey_port = valkey_port if valkey_port else int(env.get(ENV_ANSIBLE_VALKEY_PORT)) if ENV_ANSIBLE_VALKEY_PORT in env else self.valkey_port
        self.valkey_host = valkey_host if valkey_host else env.get(ENV_ANSIBLE_VALKEY_HOST) if ENV_ANSIBLE_VALKEY_HOST in env else self.valkey_host
        self.valkey_socket = valkey_socket if valkey_socket else Path(env.get(ENV_ANSIBLE_VALKEY_SOCKET)) if ENV_ANSIBLE_VALKEY_SOCKET in env else self.valkey_socket
        self.web_url = web_url if web_url else str(env.get(ENV_ANSIBLE_WEB_URL)) if ENV_ANSIBLE_WEB_URL in env else f'http://localhost:{self.web_port}{self.web_root or "/"}'
        self.ssh_keys_dir = self.ansible_dir / '.ssh'
        self.playbooks_dir = self.ansible_dir / 'playbooks'
        self.inventory_dir = self.ansible_dir / 'inventory'

    def has_valkey(self) -> bool:
        return self.valkey_host is not None or (self.valkey_socket is not None and self.valkey_socket.exists())
    
    def load(self) -> bool:
        logger = colorlog.getLogger()
        logger.debug("validating settings")
        logger.debug(f'checking if ansible save dir "{str(self.ansible_dir.absolute())}" exists')
        try:
            self.ansible_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, IOError) as exception:
            logger.error(repr(exception))
            logger.critical(f'Unable to create ansible save directory "{str(self.ansible_dir.absolute())}"')
            return False
        dummy_file: Path = self.ansible_dir / '.test'
        logger.debug(f'ensuring we can write to ansible save dir "{str(self.ansible_dir.absolute())}"')
        try:
            dummy_file.touch()
            dummy_file.unlink()
        except (PermissionError, IOError) as exception:
            logger.error(repr(exception))
            logger.critical(f'Unable to write to ansible save directory "{str(self.ansible_dir.absolute())}"')
            return False
        logger.debug(f'ensuring ansible inventory dir "{str(self.inventory_dir)}" exists')
        try:
            self.inventory_dir.mkdir(parents = True, exist_ok= True)
        except (PermissionError, IOError) as exception:
            logger.error(repr(exception))
            logger.critical(f'Unable to create ansible inventory directory "{str(self.inventory_dir.absolute())}"')
            return False
        logger.debug(f'ensuring we can write to ansible inventory dir "{str(self.inventory_dir.absolute())}"')
        dummy_file = self.inventory_dir / '.dummy'
        try:
            dummy_file.touch()
            dummy_file.unlink()
        except (PermissionError, IOError) as exception:
            logger.error(repr(exception))
            logger.critical(f'Unable to write to ansible inventory directory "{str(self.inventory_dir.absolute())}"')
            return False
        dummy_file = self.playbooks_dir / '.dummy'
        logger.debug(f'ensuring ansible playbook dir "{str(self.playbooks_dir.absolute())}" exists')
        try:
            self.playbooks_dir.mkdir(parents= True, exist_ok= True)
        except (PermissionError, IOError) as exception:
            logger.error(repr(exception))
            logger.critical(f'Unable to create ansible playbook directory "{str(self.playbooks_dir.absolute())}"')
            return False
        logger.debug(f'ensuring we can write to ansible playbook dir "{str(self.inventory_dir.absolute())}"')
        try:
            dummy_file.touch()
            dummy_file.unlink()
        except (PermissionError, IOError) as exception:
            logger.error(repr(exception))
            logger.critical(f'Unable to write to ansible playbook directory "{str(self.playbooks_dir.absolute())}"')
            return False
        logger.debug(f'ensuring ansible ssh keys dir "{str(self.ssh_keys_dir.absolute())}" exists')
        try:
            self.ssh_keys_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, IOError) as exception:
            logger.error(repr(exception))
            logger.critical(f'Unable to create ansible ssh keys directory "{str(self.ssh_keys_dir.absolute())}"')
            return False
        dummy_file = self.ssh_keys_dir / '.dummy'
        logger.debug(f'ensuring we can write to ansible ssh keys dir "{str(self.ssh_keys_dir.absolute())}"')
        try:
            dummy_file.touch()
            dummy_file.unlink()
        except (PermissionError, IOError) as exception:
            logger.error(repr(exception))
            logger.critical(f'Unable to write to ansible ssh keys directory "{str(self.ssh_keys_dir.absolute())}"')
        return True
