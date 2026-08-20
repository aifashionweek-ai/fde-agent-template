"""Structured logging (J-12): read the log, don't theorize. structlog if available, stdlib fallback."""
import logging, os, sys
try:
    import structlog
    _HAS = True
except ImportError:
    _HAS = False

def _setup():
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    if _HAS:
        procs = [structlog.contextvars.merge_contextvars, structlog.processors.add_log_level,
                 structlog.processors.TimeStamper(fmt="iso")]
        procs.append(structlog.processors.JSONRenderer() if os.getenv("LOG_JSON","0")=="1"
                     else structlog.dev.ConsoleRenderer())
        structlog.configure(processors=procs, wrapper_class=structlog.make_filtering_bound_logger(level),
                            logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))
        return structlog.get_logger("fde")
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stderr)
    lg = logging.getLogger("fde")
    class _Shim:
        def _f(self, e, **k): return e + " " + " ".join(f"{a}={b}" for a,b in k.items())
        def info(self, e, **k): lg.info(self._f(e, **k))
        def warning(self, e, **k): lg.warning(self._f(e, **k))
        def error(self, e, **k): lg.error(self._f(e, **k))
        def debug(self, e, **k): lg.debug(self._f(e, **k))
    return _Shim()
log = _setup()
