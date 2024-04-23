import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as integration test")

def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", help="Run integration tests")
    parser.addoption("--ip", action="store", help="IP address for integration tests")
    parser.addoption("--zone", default=1, action="store", help="IP address for integration tests")

def pytest_runtest_setup(item):
    """Skip tests marked 'integration' unless an ip address is given."""
    if "integration" in item.keywords and not item.config.getoption("--ip"):
        pytest.skip("use --ip and an ip address to run integration tests.")