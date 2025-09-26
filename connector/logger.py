import logging, structlog, sys

def configure_logging(level="INFO"):
    logging.basicConfig(stream=sys.stdout, level=getattr(logging, level), format="%(message)s")
    structlog.configure(
        processors=[structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.add_log_level,
                    structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    return structlog.get_logger()