import os
import shutil
import pytest
from src.model import AIBrain
from src.registry import WORKSPACE_DIR
from src.tools import ToolSystem

@pytest.fixture(autouse=True)
def clean_nexus_workspace_sandbox():
    root = os.path.abspath(WORKSPACE_DIR)
    assert os.path.basename(root) == "nexus_workspace"
    assert root != os.path.abspath(os.sep)
    if os.path.islink(root): os.unlink(root)
    elif os.path.exists(root): shutil.rmtree(root)
    os.makedirs(root, exist_ok=True)
    yield
    if os.path.islink(root): os.unlink(root)
    elif os.path.exists(root): shutil.rmtree(root)

@pytest.fixture
def mock_brain(mocker):
    brain = mocker.MagicMock(spec=AIBrain)
    brain.model = "test-reasoning-model"
    return brain

@pytest.fixture
def real_tools():
    return ToolSystem()
