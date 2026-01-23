To run locally, don't forget to create a virtual environnement

```python
python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

To run with docker

```bash
docker build -t lol-bot .

docker run -d --name lol-bot --env-file .env --restart always lol-bot
```