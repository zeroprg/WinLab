"""Chatbot channel adapters."""

from app.modules.chatbot.channels.base import BotChannel
from app.modules.chatbot.channels.telegram import TelegramChannel
from app.modules.chatbot.channels.web import WebChannel
from app.modules.chatbot.channels.yandex import YandexMessengerChannel

__all__ = [
    "BotChannel",
    "TelegramChannel",
    "WebChannel",
    "YandexMessengerChannel",
]

