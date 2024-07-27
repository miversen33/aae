from enum import Enum
from typing import Callable

class MergePolicy(Enum):
    ERROR        = 0x0000
    ACCEPT_RIGHT = 0x0002
    ACCEPT_LEFT  = 0x0001

class DictPathMergeException(Exception):
    def __init__(self, conflict_path: str) -> None:
        super().__init__(f'Conflict at path: {conflict_path} in dictionaries')

def dict_deep_merge(a: dict, b: dict, merge_policy: MergePolicy|Callable|None = MergePolicy.ERROR, path = []) -> dict:
    '''
    Does a deep merge of 2 dictionaries. Note, this mutates dict "a".

    Yoinked from: https://stackoverflow.com/a/7205107/2104990
    Very cool andrew cooke, thanks
    '''
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                dict_deep_merge(a[key], b[key], merge_policy, path + [str(key)])
            elif a[key] != b[key]:
                if callable(merge_policy):
                    a[key] = merge_policy(a[key], b[key])
                elif merge_policy == MergePolicy.ACCEPT_LEFT:
                    continue
                elif merge_policy == MergePolicy.ACCEPT_RIGHT:
                    a[key] = b[key]
                if not merge_policy or merge_policy == MergePolicy.ERROR:
                    raise DictPathMergeException('.'.join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a
