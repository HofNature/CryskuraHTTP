"""CORSManager: unified CORS header management for all services."""
from __future__ import annotations

from typing import Dict, List, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .Handler import HTTPRequestHandler
    from .Services.BaseService import BaseService


class CORSConfig:
    """CORS configuration for a service or server-wide default."""

    def __init__(
        self,
        allow_origins: Optional[List[str]] = None,
        allow_methods: Optional[List[str]] = None,
        allow_headers: Optional[List[str]] = None,
        allow_credentials: bool = False,
        expose_headers: Optional[List[str]] = None,
        max_age: int = 86400,
    ) -> None:
        self.allow_origins: List[str] = allow_origins or ["*"]
        self.allow_methods: List[str] = allow_methods or ["*"]
        self.allow_headers: List[str] = allow_headers or ["*"]
        self.allow_credentials: bool = allow_credentials
        self.expose_headers: List[str] = expose_headers or []
        self.max_age: int = max_age

    def get_headers(
        self, method: str, request_origin: Optional[str] = None
    ) -> Dict[str, str]:
        headers: Dict[str, str] = {}

        if method == "OPTIONS":
            origin = ", ".join(self.allow_origins)
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Methods"] = ", ".join(
                self.allow_methods
            )
            headers["Access-Control-Allow-Headers"] = ", ".join(
                self.allow_headers
            )
            if self.allow_credentials:
                headers["Access-Control-Allow-Credentials"] = "true"
            if self.max_age > 0:
                headers["Access-Control-Max-Age"] = str(self.max_age)
        else:
            origin_value = ", ".join(self.allow_origins)
            headers["Access-Control-Allow-Origin"] = origin_value
            if self.allow_credentials:
                headers["Access-Control-Allow-Credentials"] = "true"
            if self.expose_headers:
                headers["Access-Control-Expose-Headers"] = ", ".join(
                    self.expose_headers
                )

        return headers


class CORSManager:
    """Manages CORS configuration with per-service overrides."""

    def __init__(self, default_config: Optional[CORSConfig] = None) -> None:
        self._default: CORSConfig = default_config or CORSConfig()
        self._overrides: Dict[Type[BaseService], CORSConfig] = {}

    def set_service_override(
        self, service_class: Type[BaseService], config: CORSConfig
    ) -> None:
        self._overrides[service_class] = config

    def _get_config_for_service(
        self, service: Optional[BaseService]
    ) -> CORSConfig:
        if service is not None:
            for cls, config in self._overrides.items():
                if isinstance(service, cls):
                    return config
        return self._default

    def add_cors_headers(
        self,
        handler: HTTPRequestHandler,
        method: str,
        service: Optional[BaseService] = None,
    ) -> None:
        config = self._get_config_for_service(service)
        request_origin = handler.headers.get("Origin", None)
        headers = config.get_headers(method, request_origin)
        for key, value in headers.items():
            handler.send_header(key, value)
