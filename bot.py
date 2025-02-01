image: python:3.9

pipelines:
  default:
    - step:
        name: Setup & Run Telegram Bot
        size: 8x
        script:
          - echo "🔒 Setting up a secure bot..."

          - apt-get update && apt-get install -y git gcc python3 python3-pip

          - pip install --no-cache-dir telebot pymongo aiohttp certifi

          - mkdir -p /opt/workspace
          - cd /opt/workspace

          - git clone https://github.com/ronii432/T.git
          - cd T

          - chmod 755 bot.py
          - chmod 755 bgmi
          - python3 bot.py
