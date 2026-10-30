import test_tamper_guard


def test_package_exposes_version():
    assert test_tamper_guard.__version__ == "0.1.0"
