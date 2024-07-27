import pytest

from modules.utils import dict_deep_merge, MergePolicy, DictPathMergeException

class Test_Utils_Dict_Deep_Merge:

    def it_should_succeed(self):
        a = {1:{"a":"A"},2:{"b":"B"}}
        b = {2:{"c":"C"},3:{"d":"D"}}
        
        expected_result = {
            1: {"a": "A"},
            2: {"b": "B", "c": "C"},
            3: {"d": "D"}
        }

        assert dict_deep_merge(a, b) == expected_result

        a = {1:{"a":"A"},2:{"b":"B"}}
        b = {2:{"b":"C"},3:{"d":"D"}}

        expected_result = {
            1: {"a": "A"},
            2: {"b": "B"},
            3: {"d": "D"}
        }

        assert dict_deep_merge(a, b, MergePolicy.ACCEPT_LEFT) == expected_result
        assert dict_deep_merge(a, b, lambda left, right: left) == expected_result
        
        expected_result = {
            1: {"a": "A"},
            2: {"b": "C"},
            3: {"d": "D"}
        }
        assert dict_deep_merge(a, b, MergePolicy.ACCEPT_RIGHT) == expected_result
        assert dict_deep_merge(a, b, lambda left, right: right) == expected_result

    def it_should_throw_exception(self):
        a = {1:{"a":"A"}}
        b = {1:{"a":"C"}}
        
        with pytest.raises(DictPathMergeException):
            dict_deep_merge(a, b)

        with pytest.raises(DictPathMergeException):
            dict_deep_merge(a, b, MergePolicy.ERROR)
