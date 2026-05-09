from django.urls import re_path
from .consumer import FrontendConsumer, ESPConsumer

websocket_urlpatterns = [
    re_path(r"ws/frontend/$", FrontendConsumer.as_asgi()),
    re_path(r"ws/esp/$", ESPConsumer.as_asgi()),
]