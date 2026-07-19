from aiogram.methods import TelegramMethod
from aiogram.types import Message
from typing import Union, Dict, Any, Optional

from keyboards.theme import themed


class SendCustomMessage(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendMessage"

    chat_id: Union[int, str]
    text: str
    parse_mode: str = "HTML"
    reply_markup: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.reply_markup is not None:
            self.reply_markup = themed(self.reply_markup)


class SendCustomPhoto(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendPhoto"

    chat_id: Union[int, str]
    photo: str
    caption: str
    parse_mode: str = "HTML"
    reply_markup: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.reply_markup is not None:
            self.reply_markup = themed(self.reply_markup)


class EditCustomMessageText(TelegramMethod[Union[Message, bool]]):
    __returning__ = Union[Message, bool]
    __api_method__ = "editMessageText"

    chat_id: Union[int, str]
    message_id: int
    text: str
    parse_mode: str = "HTML"
    reply_markup: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.reply_markup is not None:
            self.reply_markup = themed(self.reply_markup)


class EditCustomMessageMedia(TelegramMethod[Union[Message, bool]]):
    __returning__ = Union[Message, bool]
    __api_method__ = "editMessageMedia"

    chat_id: Union[int, str]
    message_id: int
    media: Dict[str, Any]
    reply_markup: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.reply_markup is not None:
            self.reply_markup = themed(self.reply_markup)
