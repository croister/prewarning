import pytest

from utils.singleton import Singleton, _Singleton


class TestSingletonMetaclass:
    def test_same_instance(self):
        class MySingleton(metaclass=_Singleton):
            pass

        a = MySingleton()
        b = MySingleton()
        assert a is b

    def test_has_instance(self):
        class TestHas(metaclass=_Singleton):
            pass

        assert TestHas not in _Singleton._instances
        TestHas()
        assert TestHas in _Singleton._instances

    def test_get_instance(self):
        class TestGet(metaclass=_Singleton):
            pass

        instance = TestGet()
        assert _Singleton._instances[TestGet] is instance

    def test_different_classes_independent(self):
        class A(metaclass=_Singleton):
            pass

        class B(metaclass=_Singleton):
            pass

        a = A()
        b = B()
        assert a is not b

    def test_args_passed_to_init(self):
        class WithArgs(metaclass=_Singleton):
            def __init__(self, value):
                self.value = value

        instance = WithArgs(42)
        assert instance.value == 42
        same = WithArgs(99)
        assert same is instance
        assert same.value == 42

    def test_has_instance_method(self):
        class TestClass(metaclass=_Singleton):
            pass

        assert TestClass.has_instance() is False
        TestClass()
        assert TestClass.has_instance() is True

    def test_get_instance_method(self):
        class TestClass(metaclass=_Singleton):
            pass

        with pytest.raises(KeyError):
            TestClass.get_instance()
        instance = TestClass()
        assert TestClass.get_instance() is instance


class TestSingletonConcreteClass:
    def test_is_singleton(self):
        a = Singleton()
        b = Singleton()
        assert a is b
