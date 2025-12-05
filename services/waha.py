import requests
import os


class Waha:

    def __init__(self, api_url=None, base_url=None, url=None):
        self.__api_url = api_url or base_url or url or os.getenv("WAHA_API_URL", "http://waha:3000")
        self.base_url = self.__api_url
        self.__api_key = os.getenv("WAHA_API_KEY", "")

    def _get_headers(self):
        headers = {
            'Content-Type': 'application/json',
        }
        if self.__api_key:
            headers['X-Api-Key'] = self.__api_key
        return headers

    def send_message(self, chat_id, message):
        url = f'{self.__api_url}/api/sendText'
        payload = {
            'session': 'default',
            'chatId': chat_id,
            'text': message,
        }
        requests.post(
            url=url,
            json=payload,
            headers=self._get_headers(),
        )

    def get_history_messages(self, chat_id, limit):
        url = f'{self.__api_url}/api/default/chats/{chat_id}/messages?limit={limit}&downloadMedia=false'
        response = requests.get(
            url=url,
            headers=self._get_headers(),
        )
        return response.json()

    def start_typing(self, chat_id):
        url = f'{self.__api_url}/api/startTyping'
        payload = {
            'session': 'default',
            'chatId': chat_id,
        }
        requests.post(
            url=url,
            json=payload,
            headers=self._get_headers(),
        )

    def stop_typing(self, chat_id):
        url = f'{self.__api_url}/api/stopTyping'
        payload = {
            'session': 'default',
            'chatId': chat_id,
        }
        requests.post(
            url=url,
            json=payload,
            headers=self._get_headers(),
        )