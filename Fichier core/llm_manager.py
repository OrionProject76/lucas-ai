import requests
from queue import Queue
from threading import Thread

class LLMManager:
    def __init__(self):
        self.queue = Queue()
        self.thread = Thread(target=self.process_responses)
        self.thread.start()

    def generate(self, prompt):
        response = requests.post('http://localhost:11434/api/generate', json={'prompt': prompt}, stream=True)
        for token in response.iter_lines(decode_unicode=True):
            if token:
                self.queue.put(token)

    def process_responses(self):
        while True:
            token = self.queue.get()
            # Émettre un signal à chaque token reçu
            print(f"Token reçu : {token}")
