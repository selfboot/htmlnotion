import asyncio
import pytest
import time
import os
import random
import string
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
from html2notion.translate.batch_import import BatchImport
from html2notion.translate.cos_uploader import TencentCosUploaderAsync


def log_only_local(content):
    if 'GITHUB_ACTIONS' in os.environ:
        return

    from html2notion.utils import logger
    logger.info(content)


@pytest.fixture(scope="session", autouse=True)
def prepare_conf_fixture():
    if 'GITHUB_ACTIONS' not in os.environ:
        from html2notion.utils import test_prepare_conf
        test_prepare_conf()
        log_only_local("prepare_conf_fixture")


async def mock_cos_upload_request(file_path, *args, **kwargs):
    if 'GITHUB_ACTIONS' not in os.environ:
        from html2notion.utils import config
        secret_id = config["cos"]["secret_id"]
        secret_key = config["cos"]["secret_key"]
        region = config["cos"]["region"]
        bucket = config["cos"]["bucket"]
    else:
        secret_id = os.environ['COS_SECRET_ID']
        secret_key = os.environ['COS_SECRET_KEY']
        region = os.environ['COS_REGION']
        bucket = os.environ['COS_BUCKET']

    log_only_local(f"mock_cos_upload_request: {file_path}")
    uploader = TencentCosUploaderAsync(secret_id, secret_key, region, bucket)
    loop = asyncio.get_event_loop()
    key = f"test_workflow/{file_path.name}"
    upload_response = await uploader.upload_file(loop, file_path, key)
    log_only_local(f"Upload response: {upload_response}")

    if await uploader.check_file_exist(loop, key):
        return True
    else:
        return False


@pytest.fixture()
def temp_dir_fixture():
    with TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)
        temp_files = []
        for i in range(100):
            file_size = random.randint(1 * 1024 * 1024, 5 * 1024 * 1024)
            random_text = "".join(random.choices(string.ascii_letters + string.digits, k=file_size))

            temp_file = dir_path / f"file_{i}.txt"
            temp_file.write_text(random_text)
            temp_files.append(temp_file)

        yield dir_path


@pytest.mark.asyncio
async def test_batch_cos_upload(temp_dir_fixture):
    concurrent_limit = 10
    dir_path = temp_dir_fixture
    with patch("html2notion.translate.notion_import.NotionImporter.process_file", side_effect=mock_cos_upload_request):
        batch_processor = BatchImport(dir_path, concurrent_limit=concurrent_limit)
        responses = await batch_processor.process_directory()

    for res in responses:
        assert (res)
