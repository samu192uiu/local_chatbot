# src/zapwaha/services/waha.py
import os
import requests
from typing import Optional


class WahaClient:
    """Cliente para interagir com a API do WAHA"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or os.getenv("WAHA_API_URL", "http://waha:3000")
        self.api_key = api_key or os.getenv("WAHA_API_KEY", "")
        self.session = os.getenv("WAHA_SESSION", "default")
    
    def _get_headers(self) -> dict:
        headers = {
            'Content-Type': 'application/json',
        }
        if self.api_key:
            headers['X-Api-Key'] = self.api_key
        return headers
    
    def send_text(self, chat_id: str, text: str) -> dict:
        url = f'{self.base_url}/api/sendText'
        payload = {
            'session': self.session,
            'chatId': chat_id,
            'text': text,
        }
        response = requests.post(url, json=payload, headers=self._get_headers())
        return response.json()
    
    def send_buttons(self, chat_id: str, text: str, buttons: list) -> dict:
        url = f'{self.base_url}/api/sendButtons'
        payload = {
            'session': self.session,
            'chatId': chat_id,
            'text': text,
            'buttons': buttons,
        }
        response = requests.post(url, json=payload, headers=self._get_headers())
        return response.json()
    
    def start_typing(self, chat_id: str):
        url = f'{self.base_url}/api/startTyping'
        payload = {
            'session': self.session,
            'chatId': chat_id,
        }
        requests.post(url, json=payload, headers=self._get_headers())
    
    def stop_typing(self, chat_id: str):
        url = f'{self.base_url}/api/stopTyping'
        payload = {
            'session': self.session,
            'chatId': chat_id,
        }
        requests.post(url, json=payload, headers=self._get_headers())
