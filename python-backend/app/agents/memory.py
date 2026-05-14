from threading import RLock

from app.core.config import settings


_memory_store: dict[int, list[dict[str, str]]] = {}
_memory_lock = RLock()


def get_history(memory_id: int) -> list[dict[str, str]]:
    with _memory_lock:
        return [message.copy() for message in _memory_store.get(memory_id, [])]


def append_user_message(memory_id: int, content: str) -> None:
    _append_message(memory_id=memory_id, role="user", content=content)


def append_assistant_message(memory_id: int, content: str) -> None:
    _append_message(memory_id=memory_id, role="assistant", content=content)


def trim_history(memory_id: int) -> None:
    with _memory_lock:
        history = _memory_store.get(memory_id, [])
        max_messages = settings.max_memory_messages
        if max_messages == 0:
            _memory_store[memory_id] = []
            return
        if len(history) > max_messages:
            _memory_store[memory_id] = history[-max_messages:]


def _append_message(memory_id: int, role: str, content: str) -> None:
    with _memory_lock:
        _memory_store.setdefault(memory_id, []).append({"role": role, "content": content})
        trim_history(memory_id)
