"""Opt-in Langfuse tracing. Only operational metadata is exported."""
import logging
import os
from contextlib import contextmanager
from functools import lru_cache, wraps

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def client():
    if os.getenv("DXA_TRACE") != "1":
        return None
    keys = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    if not all(os.getenv(key) for key in keys):
        log.warning("DXA tracing requires Langfuse URL and project keys")
        return None
    try:
        from langfuse import Langfuse
        return Langfuse(host=os.environ["LANGFUSE_BASE_URL"],
                        environment=os.getenv("DXA_TRACE_ENV", "dana-local"))
    except Exception:
        log.warning("Could not initialize Dana tracing")
        return None


def update(span, **fields):
    if span is not None:
        try:
            span.update(**fields)
        except Exception:
            log.warning("Could not update Dana observation")


@contextmanager
def observe(name, kind="span", **fields):
    lf = client()
    if lf is None:
        yield None
        return
    try:
        manager = lf.start_as_current_observation(name=name, as_type=kind, **fields)
        span = manager.__enter__()
    except Exception:
        log.warning("Could not start Dana observation")
        yield None
        return
    try:
        yield span
    except Exception as error:
        update(span, level="ERROR", status_message=type(error).__name__)
        raise
    finally:
        try:
            manager.__exit__(None, None, None)
        except Exception:
            log.warning("Could not close Dana observation")


def traced(name, kind="span", summarize=None):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            with observe(name, kind) as span:
                result = fn(*args, **kwargs)
                if span is not None and summarize is not None:
                    update(span, metadata=summarize(result))
                return result
        return wrapped
    return decorate


def result_metadata(result):
    return {key: result[key] for key in ("mode", "status", "refused", "answered_by") if key in result} | {
        "warnings": len(result.get("warnings") or []),
        "actions": [action.get("action") for action in result.get("actions", [])],
    }


def generation_usage(span, response):
    usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
    if usage is None:
        return
    fields = {}
    for key, names in {
        "input": ("prompt_token_count", "prompt_tokens"),
        "output": ("candidates_token_count", "completion_tokens"),
        "total": ("total_token_count", "total_tokens"),
    }.items():
        for name in names:
            value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
            if isinstance(value, int):
                fields[key] = value
                break
    if fields:
        update(span, usage_details=fields)


def instrument_dana():
    """Observe the pinned Dana SDK completion boundary without exporting payloads."""
    if client() is None:
        return
    from dana.common.sys_resource.llm.llm_query_executor import LLMQueryExecutor
    original = LLMQueryExecutor.query_once
    if getattr(original, "_dxa_traced", False):
        return

    @wraps(original)
    async def query_once(self, *args, **kwargs):
        with observe("dana.reason", "generation") as span:
            response = await original(self, *args, **kwargs)
            content = getattr(response, "content", response)
            if isinstance(content, dict):
                model = content.get("model")
                if model:
                    update(span, model=model)
                from types import SimpleNamespace
                generation_usage(span, SimpleNamespace(usage=content.get("usage")))
            if getattr(response, "success", True) is False:
                update(span, level="ERROR", status_message="Dana completion failed")
            return response

    query_once._dxa_traced = True
    LLMQueryExecutor.query_once = query_once
