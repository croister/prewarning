import inspect
from abc import ABC, abstractmethod


def add_sources(classes, sources_dict, subclass_map=None):
    for cls in classes:
        subclasses = (
            (subclass_map or {}).get(cls, cls.__subclasses__())
            if subclass_map is not None
            else cls.__subclasses__()
        )
        if not inspect.isabstract(cls):
            sources_dict[cls.name] = cls
        add_sources(subclasses, sources_dict, subclass_map=subclass_map)


class _MockAbstractBase(ABC):
    name: str

    @abstractmethod
    def required_method(self):
        pass


class _ConcreteBase(_MockAbstractBase):
    name = "ConcreteBase"

    def required_method(self):
        pass


class SubSource(_ConcreteBase):
    name = "SubSource"


class StillAbstract(_MockAbstractBase):
    name = "StillAbstract"
    # no required_method -> still abstract


class ConcreteStillAbstract(StillAbstract):
    name = "ConcreteStillAbstract"

    def required_method(self):
        pass


class TestAddSources:
    def test_adds_concrete_class(self):
        result = {}
        add_sources([_ConcreteBase], result, subclass_map={_ConcreteBase: []})
        assert "ConcreteBase" in result
        assert result["ConcreteBase"] is _ConcreteBase

    def test_skips_abstract(self):
        result = {}
        add_sources([StillAbstract], result, subclass_map={StillAbstract: []})
        assert "StillAbstract" not in result

    def test_recurses_into_subclasses(self):
        result = {}
        add_sources(
            [_ConcreteBase],
            result,
            subclass_map={
                _ConcreteBase: [SubSource],
                SubSource: [],
            },
        )
        assert "ConcreteBase" in result
        assert "SubSource" in result

    def test_handles_empty_list(self):
        result = {}
        add_sources([], result)
        assert len(result) == 0

    def test_skips_abstract_but_adds_concrete_subclass(self):
        result = {}
        add_sources(
            [StillAbstract],
            result,
            subclass_map={
                StillAbstract: [ConcreteStillAbstract],
                ConcreteStillAbstract: [],
            },
        )
        assert "StillAbstract" not in result
        assert "ConcreteStillAbstract" in result
