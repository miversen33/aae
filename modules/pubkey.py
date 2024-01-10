from pathlib import Path
from time import time

VALID_ACCESS_METHODS = {"FILE"}
CACHE_PULL_TTL = 60

class MissingPubkeyException(Exception):
    def __init__(self, pubkey_location: str):
        super().__init__(f'Pubkey "{pubkey_location}" does not exist')

class InvalidPubkeyAccessMethodException(Exception):
    def __init__(self, invalid_am: str):
        super().__init__(f'''Invalid Pubkey Access Method: "{invalid_am}".  Valid PUBKEY_STORE values are {", ".join([f'"{am}"' for am in VALID_ACCESS_METHODS])}''')

class Pubkey:
    pubkey_location: str
    pubkey_access_method: str
    pubkey_as_str: str
    __last_pull: float = -1.0
    def __init__(self, pubkey_location: str, pubkey_access_method: str):
        valid_am = False
        for am in VALID_ACCESS_METHODS:
            if valid_am:
                break
            valid_am = pubkey_access_method.upper() == am
        if not valid_am:
            raise InvalidPubkeyAccessMethodException(pubkey_access_method)
        self.pubkey_location = pubkey_location
        self.pubkey_access_method = pubkey_access_method

    def __repr__(self) -> str:
        return f'<Pubkey(pubkey_location = "{self.pubkey_location}", pubkey_access_method = "{self.pubkey_access_method}")'

    def _load_pubkey_as_file(self) -> str:
        pubkey = Path(self.pubkey_location)
        if not pubkey.exists():
            raise MissingPubkeyException(self.pubkey_location)
        raw_pubkey = ""
        with open(pubkey) as _in_file:
            raw_pubkey = _in_file.read()
        return raw_pubkey

    def load(self, force: bool = False):
        if not force and self.__last_pull + CACHE_PULL_TTL > time():
            # Nothing to do here
            return
        # Try to load the pubkey. If we fail, complain, maybe have this break instead of toss a bool?
        if self.pubkey_access_method == 'FILE':
            self.pubkey_as_str = self._load_pubkey_as_file()
        else:
            raise InvalidPubkeyAccessMethodException(self.pubkey_access_method)

        self.__last_pull = time()

    def __str__(self) -> str:
        self.load()
        return self.pubkey_as_str

