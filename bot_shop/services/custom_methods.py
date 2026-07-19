from aiogram.methods import TelegramMethod
from aiogram.types import Message
from typing import Union, Dict, Any, Optional

class SendCustomMessage(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendMessage"

    chat_id: Union[int, str]
    text: str
    parse_mode: str = "HTML"
    reply_markup: Optional[Dict[str, Any]] = None

class SendCustomPhoto(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendPhoto"

    chat_id: Union[int, str]
    photo: str
    caption: str
    parse_mode: str = "HTML"
    reply_markup: Optional[Dict[str, Any]] = None

class EditCustomMessageText(TelegramMethod[Union[Message, bool]]):
    __returning__ = Union[Message, bool]
    __api_method__ = "editMessageText"

    chat_id: Union[int, str]
    message_id: int
    text: str
    parse_mode: str = "HTML"
    reply_markup: Optional[Dict[str, Any]] = None

class EditCustomMessageMedia(TelegramMethod[Union[Message, bool]]):
    __returning__ = Union[Message, bool]
    __api_method__ = "editMessageMedia"

    chat_id: Union[int, str]
    message_id: int
    media: Dict[str, Any]
    reply_markup: Optional[Dict[str, Any]] = None
