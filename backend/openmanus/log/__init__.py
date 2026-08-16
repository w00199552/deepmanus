from __future__ import annotations

from loguru import logger as _real_logger

from openmanus.log.logger import setup_logger

__all__ = ["logger", "setup_logger"]

class _StdlibCompatLogger:

    __slots__ = ()

    @staticmethod
    def _format(msg: str, args: tuple) -> str:
        if not args:
            return msg
        try:
            return msg % args
        except (TypeError, ValueError):
            return msg

    def debug(self, msg: str, *args, **kwargs) -> None:
        _real_logger.opt(depth=1).debug(self._format(msg, args), **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        _real_logger.opt(depth=1).info(self._format(msg, args), **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        _real_logger.opt(depth=1).warning(self._format(msg, args), **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        _real_logger.opt(depth=1).error(self._format(msg, args), **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        _real_logger.opt(depth=1).critical(self._format(msg, args), **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        _real_logger.opt(depth=1).exception(self._format(msg, args), **kwargs)

    def __getattr__(self, name: str):
        return getattr(_real_logger, name)

logger = _StdlibCompatLogger()
