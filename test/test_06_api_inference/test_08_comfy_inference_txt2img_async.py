import logging

import config as config
from utils.api import Api
from utils.helper import update_oas, comfy_execute_create

logger = logging.getLogger(__name__)


class TestTxt2ImgInferenceAsyncAfterComfyE2E:

    def setup_class(self):
        self.api = Api(config)
        update_oas(self.api)

    @classmethod
    def teardown_class(self):
        pass

    def test_1_comfy_txt2img_async_create(self):
        comfy_execute_create(1, self.api, config.comfy_async_ep_name)
