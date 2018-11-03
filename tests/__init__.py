import pytest

# https://stackoverflow.com/a/43938191
#
# from . import longrun
#
# @longrun
# def test_long():
#   pass

longrun = pytest.mark.skipif(
    not pytest.config.option.longrun,
    reason="needs --longrun option to run")
