import asyncio
import pytest
import pytest_asyncio

from vsslctrl import VSSL_VERSION
from vsslctrl.data_structure import ModelIDs
from vsslctrl.device import Models


class TestDevice:
    @pytest.mark.asyncio
    async def test_device_models(self):
        model = Models.A1X.value
        assert model.model_id == ModelIDs.A1X

        model = Models.get_by_name("A.1x")
        assert model.model_id == ModelIDs.A1X
        assert model.model_id != ModelIDs.A1
        assert model.name == "A.1x"
        assert len(model.zones) == 1

        model = Models.get_by_name("A1")
        assert model.model_id != ModelIDs.A1X
        assert model.model_id == ModelIDs.A1

        model = Models.get_by_id(ModelIDs.A1X)
        assert model.model_id == ModelIDs.A1X

        model = Models.get_by_id("11")
        assert model.model_id == ModelIDs.A1X

        model = Models.get_by_name("random string")
        assert model == None

        model = Models.get_by_id(10)
        assert model == None

        model = Models.get_by_id("random string")
        assert model == None

        model = Models.get_by_id(ModelIDs.A3X)
        assert model.model_id == ModelIDs.A3X
        assert len(model.zones) == 3

        model = Models.get_by_id(ModelIDs.A3)
        assert model.model_id == ModelIDs.A3
        assert len(model.zones) == 3

        model = Models.get_by_id(ModelIDs.A6X)
        assert model.model_id == ModelIDs.A6X
        assert len(model.zones) == 6

        model = Models.get_by_id(ModelIDs.A6)
        assert model.model_id == ModelIDs.A6
        assert len(model.zones) == 6

        # Test Find
        model = Models.find("A.1x")
        assert model.model_id == ModelIDs.A1X
        assert model.model_id != ModelIDs.A1
        assert model.name == "A.1x"
        assert len(model.zones) == 1
        assert Models.is_valid(model)

        model = Models.find("vssl A.6x")
        assert model.model_id == ModelIDs.A6X
        assert model.model_id != ModelIDs.A6
        assert model.name == "A.6x"
        assert len(model.zones) == 6

        model = Models.find("vssl A6")
        assert model.model_id == ModelIDs.A6
        assert model.model_id != ModelIDs.A6X
        assert model.name == "A.6"
        assert len(model.zones) == 6

        model = Models.find("A  3")
        assert model.model_id == ModelIDs.A3
        assert model.model_id != ModelIDs.A3X
        assert model.name == "A.3"
        assert len(model.zones) == 3

        model = Models.find("VSSL A.3x")
        assert model.model_id == ModelIDs.A3X
        assert model.model_id != ModelIDs.A3
        assert model.name == "A.3x"
        assert len(model.zones) == 3
