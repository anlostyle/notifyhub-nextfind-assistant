import asyncio
import datetime
import logging
import threading
from dataclasses import dataclass
from typing import Dict, Optional
from xml.etree.ElementTree import fromstring

import httpx
from cacheout import Cache
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from tenacity import retry, stop_after_attempt, wait_random_exponential

from notifyhub.common.response import json_500
from notifyhub.plugins.components.qywx_Crypt.WXBizMsgCrypt import WXBizMsgCrypt

from .nextfind import handle_command
from .utils import config

LOG_PREFIX = "「NextFind 企业微信助手」"
HTTP_TIMEOUT = 30
TOKEN_EXPIRE_BUFFER = 500
logger = logging.getLogger(__name__)
token_cache = Cache(maxsize=1)
nextfind_assistant_router = APIRouter(prefix="/nextfind_assistant", tags=["nextfind_assistant"])


@dataclass
class QywxMessage:
    content: str
    from_user: str
    to_user: str
    create_time: str
    msg_type: str
    msg_id: str


class QywxMessageSender:
    @retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=20))
    def get_access_token(self) -> Optional[str]:
        cached_token = token_cache.get("access_token")
        expires_time = token_cache.get("expires_time")
        if expires_time and expires_time >= datetime.datetime.now() and cached_token:
            return cached_token
        if not all([config.qywx_base_url, config.sCorpID, config.sCorpsecret]):
            return None
        res = httpx.get(
            f"{config.qywx_base_url.strip('/')}/cgi-bin/gettoken",
            params={"corpid": config.sCorpID, "corpsecret": config.sCorpsecret},
            timeout=HTTP_TIMEOUT,
        )
        data = res.json()
        if data.get("errcode") != 0:
            logger.error("%s 获取企业微信 token 失败: %s", LOG_PREFIX, data)
            return None
        ttl = int(data["expires_in"]) - TOKEN_EXPIRE_BUFFER
        expires_at = datetime.datetime.now() + datetime.timedelta(seconds=ttl)
        token_cache.set("access_token", data["access_token"], ttl=ttl)
        token_cache.set("expires_time", expires_at, ttl=ttl)
        return data["access_token"]

    def send_text_message(self, text: str, to_user: str) -> bool:
        token = self.get_access_token()
        if not token:
            return False
        payload = {
            "touser": to_user,
            "agentid": config.sAgentid,
            "msgtype": "text",
            "text": {"content": text},
        }
        data = httpx.post(
            f"{config.qywx_base_url.strip('/')}/cgi-bin/message/send",
            params={"access_token": token},
            json=payload,
            timeout=HTTP_TIMEOUT,
        ).json()
        if data.get("errcode") != 0:
            logger.error("%s 发送企业微信消息失败: %s", LOG_PREFIX, data)
            return False
        return True


class QywxProcessor:
    def __init__(self):
        self._crypto = None

    def crypto(self):
        if self._crypto is None:
            if not all([config.sToken, config.sEncodingAESKey, config.sCorpID]):
                raise ValueError("企业微信加密配置不完整")
            self._crypto = WXBizMsgCrypt(config.sToken, config.sEncodingAESKey, config.sCorpID)
        return self._crypto

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        ret, echo = self.crypto().VerifyURL(msg_signature, timestamp, nonce, echostr)
        if ret != 0:
            raise ValueError("企业微信 URL 验证失败")
        return echo.decode("utf-8")

    def parse(self, xml_data: str) -> QywxMessage:
        root = fromstring(xml_data)
        data: Dict[str, str] = {node.tag: node.text or "" for node in root}
        return QywxMessage(
            content=data.get("Content", ""),
            from_user=data.get("FromUserName", ""),
            to_user=data.get("ToUserName", ""),
            create_time=data.get("CreateTime", ""),
            msg_type=data.get("MsgType", ""),
            msg_id=data.get("MsgId", ""),
        )

    def handle_message(self, encrypted_msg: str, msg_signature: str, timestamp: str, nonce: str):
        ret, decrypted = self.crypto().DecryptMsg(encrypted_msg, msg_signature, timestamp, nonce)
        if ret != 0:
            raise ValueError("企业微信消息解密失败")
        message = self.parse(decrypted.decode("utf-8"))
        if message.msg_type == "text":
            NextFindThread(message).start()


class NextFindThread(threading.Thread):
    def __init__(self, message: QywxMessage):
        super().__init__(name="NextFindAssistantThread")
        self.message = message
        self.sender = QywxMessageSender()

    def split_text(self, text: str):
        max_len = 768
        return [text[i : i + max_len] for i in range(0, len(text), max_len)] or [text]

    def run(self):
        try:
            result = asyncio.run(handle_command(self.message.from_user, self.message.content))
            for segment in self.split_text(result):
                self.sender.send_text_message(segment, self.message.from_user)
        except Exception as e:
            logger.error("%s 处理失败: %s", LOG_PREFIX, e, exc_info=True)
            self.sender.send_text_message("处理失败：" + str(e), self.message.from_user)


processor = QywxProcessor()


@nextfind_assistant_router.get("/chat")
async def verify_callback(request: Request):
    try:
        msg_signature = request.query_params.get("msg_signature")
        timestamp = request.query_params.get("timestamp")
        nonce = request.query_params.get("nonce")
        echostr = request.query_params.get("echostr")
        if not all([msg_signature, timestamp, nonce, echostr]):
            raise HTTPException(status_code=400, detail="缺少必要参数")
        return int(processor.verify_url(msg_signature, timestamp, nonce, echostr))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("%s URL 验证失败: %s", LOG_PREFIX, e, exc_info=True)
        return json_500("URL 验证失败")


@nextfind_assistant_router.post("/chat")
async def receive_message(request: Request):
    try:
        msg_signature = request.query_params.get("msg_signature")
        timestamp = request.query_params.get("timestamp")
        nonce = request.query_params.get("nonce")
        if not all([msg_signature, timestamp, nonce]):
            raise HTTPException(status_code=400, detail="缺少必要参数")
        body = (await request.body()).decode("utf-8")
        processor.handle_message(body, msg_signature, timestamp, nonce)
        return Response(content="success", media_type="text/plain")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("%s 消息处理失败: %s", LOG_PREFIX, e, exc_info=True)
        return json_500("消息处理失败")
