# src/zapwaha/state/memory.py
from __future__ import annotations
import logging
from typing import Dict, Any

logger = logging.getLogger("ZapWaha")

class MemoryStateManager:
    def __init__(self):
        # { chat_id: { "state": "...", ...dados temporários... } }
        self._store: Dict[str, Dict[str, Any]] = {}

    def get_state(self, chat_id: str) -> str:
        return self._store.get(chat_id, {}).get("state", "MENU_PRINCIPAL")

    def set_state(self, chat_id: str, state: str, data: Dict[str, Any] | None = None) -> None:
        current = self._store.get(chat_id, {})
        current["state"] = state
        if data:
            current.update(data)
        self._store[chat_id] = current
        logger.debug(f"set_state({chat_id}, {state}, data={data})")

    def update_data(self, chat_id: str, **kwargs) -> None:
        current = self._store.get(chat_id, {})
        if "state" not in current:
            current["state"] = "MENU_PRINCIPAL"
        current.update(kwargs)
        self._store[chat_id] = current
        logger.debug(f"update_data({chat_id}, {kwargs})")

    def get_data(self, chat_id: str) -> Dict[str, Any]:
        return self._store.get(chat_id, {})

    def clear_data(self, chat_id: str) -> None:
        state = self.get_state(chat_id)
        self._store[chat_id] = {"state": state}
        logger.debug(f"clear_data({chat_id}) -> keep state={state}")

    def delete_state(self, chat_id: str) -> None:
        if chat_id in self._store:
            del self._store[chat_id]
            logger.debug(f"delete_state({chat_id})")

# singleton usado pelo fluxo
state_manager = MemoryStateManager()
