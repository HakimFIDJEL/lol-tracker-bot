To run locally, don't forget to create a virtual environnement

```python
python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python bot.py
```

To run with docker

```bash
# First, build the container
docker build -t lol-bot .

# Then run it
docker run -d --name lol-bot --env-file .env --restart always lol-bot

# If needed, remove it
docker rm -f lol-bot
```