# Render Blueprint fayli.
# Render Dashboard > New > Blueprint orqali shu faylni o'z ichiga olgan
# GitHub repo'ni ulasangiz, Render avtomatik ravishda:
#   1) bepul Postgres ma'lumotlar bazasini,
#   2) bepul web-servis (botning o'zi)ni
# yaratadi va ularni DATABASE_URL orqali bir-biriga ulaydi.
#
# Faqat BOT_TOKEN ni qo'lda kiritishingiz kerak bo'ladi (xavfsizlik uchun
# sync: false qilib qo'yilgan — Render sizdan shu qiymatni so'raydi).

databases:
  - name: brainrot-db
    plan: free
    databaseName: brainrot
    user: brainrot

services:
  - type: web
    name: brainrot-trade-bot
    runtime: python
    plan: free
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python webhook_app.py"
    envVars:
      - key: BOT_TOKEN
        sync: false
      - key: DATABASE_URL
        fromDatabase:
          name: brainrot-db
          property: connectionString
      - key: PYTHON_VERSION
        value: "3.11.9"
