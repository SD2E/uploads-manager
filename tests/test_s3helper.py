"""Tests for code in reactor.py"""
import os
import sys
import yaml
import json
import pytest
from attrdict import AttrDict

CWD = os.getcwd()
HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
# sys.path.insert(0, '/')
sys.path.insert(0, CWD)
sys.path.insert(0, PARENT)

from fixtures import credentials, agave, settings
from . import longrun


@pytest.fixture()
def s3bucket(settings):
    return 'uploads'


@pytest.fixture()
def s3root(settings):
    return os.path.join(CWD, 'tests/data/corral/s3/ingest')


@pytest.fixture()
def dataroot(settings):
    return os.path.join(CWD, 'tests/data/work/projects/SD2E-Community/prod/data')


@pytest.fixture()
def s3helper(settings, s3root, dataroot, monkeypatch):
    import s3helpers
    monkeypatch.setenv('TACC_S3_ROOTDIR', s3root)
    sh = s3helpers.S3Helper()
    return sh


@pytest.fixture()
def agavehelper(settings, agave, dataroot, monkeypatch):
    from datacatalog.agavehelpers import AgaveHelper
    monkeypatch.setenv('CATALOG_ROOT_DIR', dataroot)
    monkeypatch.setenv('CATALOG_STORAGE_SYSTEM', 'virtual_filesystem')
    ah = AgaveHelper(agave)
    return ah


def test_env_vars(s3helper):
    assert s3helper.BUCKET.startswith('uploads') is True
    assert s3helper.STORAGE_PREFIX.startswith('/corral') is False


def test_from_s3_uri(s3helper):
    bucket, path, name = s3helper.from_s3_uri('s3://uploads/emerald/201809/protein.png')
    assert bucket == 'uploads'
    assert path == 'emerald/201809'
    assert name == 'protein.png'


def test_mapped_bucket_path(s3helper, s3bucket, s3root):
    dest = os.path.join(s3root, s3bucket, 'emerald/201808/protein.png')
    pp = s3helper.mapped_bucket_path('emerald/201808/protein.png')
    assert pp == dest
    pp = s3helper.mapped_bucket_path('/emerald/201808/protein.png')
    assert pp == dest
    dest = s3helper.mapped_bucket_path(pp)
    assert pp == dest


def test_mapped_catalog_path(s3helper, s3bucket, s3root):
    dest = os.path.join(s3root, s3bucket, 'emerald/201808/protein.png')
    pp = s3helper.mapped_catalog_path('uploads/emerald/201808/protein.png')
    assert pp == dest
    pp = s3helper.mapped_catalog_path('/uploads/emerald/201808/protein.png')
    assert pp == dest
    dest = s3helper.mapped_catalog_path(pp)
    assert pp == dest


def test_exists(s3helper, s3bucket):
    assert s3helper.exists('uploads/emerald/201808/protein.png', s3bucket) is True


def test_isfile(s3helper, s3bucket):
    assert s3helper.isfile('/uploads/emerald/201808/protein.png', s3bucket) is True
    assert s3helper.isfile('uploads/emerald/201808/protein.png', s3bucket) is True
    assert s3helper.isfile('uploads/emerald/201808/', s3bucket) is False
    assert s3helper.isfile('uploads/emerald/201808', s3bucket) is False


def test_isdir(s3helper, s3bucket):
    assert s3helper.isdir('/uploads/emerald/201808/protein.png', s3bucket) is False
    assert s3helper.isdir('uploads/emerald/201808/protein.png', s3bucket) is False
    assert s3helper.isdir('uploads/emerald/201808/', s3bucket) is True
    assert s3helper.isdir('uploads/emerald/201808', s3bucket) is True


def test_listdir(s3helper, s3bucket):
    # list subdir allowing directories
    assert s3helper.listdir(
        'uploads/emerald/201808', s3bucket) == [
            'uploads/emerald/201808/dna',
            'uploads/emerald/201808/protein.png',
            'uploads/emerald/201808/dna/sequence.fa']

    # list subdir filtering directories
    assert s3helper.listdir('uploads/emerald/201808', bucket=s3bucket,
                            directories=False) == [
                                'uploads/emerald/201808/protein.png', 'uploads/emerald/201808/dna/sequence.fa']

    # list higher up,  filtering directories
    assert s3helper.listdir('uploads/emerald', bucket=s3bucket,
                            directories=False) == [
                                'uploads/emerald/201808/protein.png', 'uploads/emerald/201808/dna/sequence.fa']


def test_paths_to_uris(s3helper, s3bucket):
    filepaths = s3helper.listdir(
        'uploads/emerald/201808', bucket=s3bucket, directories=False)
    assert s3helper.paths_to_s3_uris(
        filepaths, bucket=s3bucket) == [
            's3://uploads/emerald/201808/protein.png',
            's3://uploads/emerald/201808/dna/sequence.fa']


@longrun
def test_agavehelper_exists(agavehelper, s3helper):
    assert agavehelper.exists('/uploads/doesnotexist', storage_system='data-sd2e-community') is False
    assert agavehelper.exists('/uploads', storage_system='data-sd2e-community') is True


@longrun
def test_agavehelper_exists_localhost(agavehelper, s3helper):
    assert agavehelper.exists('/uploads/doesnotexist') is False
    assert agavehelper.exists('/uploads') is True

# def test_listdir_posix(agavehelper):
#     monkeypatch.setenv('CATALOG_STORAGE_SYSTEM', 'virtual_filesystem')
#     monkeypatch.setenv('CATALOG_ROOT_DIR', os.path.join(PARENT, 'tests/virtual_filesystem'))
#     monkeypatch.setenv('CATALOG_FILES_API_PAGESIZE', '50')
#     h = datacatalog.agavehelpers.AgaveHelper(agave)
#     listing = h.listdir_agave_posix('/sample/tacc-cloud/agavehelpers/upload', recurse=True,
#                                     storage_system='virtual_filesystem', directories=True)
#     assert '/sample/tacc-cloud/agavehelpers/upload/biofab/abcd' in listing
