# test_mongo.py

from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=30000)
try:
    # The ismaster command is cheap and does not require auth.
    print(client.admin.command('ismaster'))
    print("Connection successful!")
except Exception as e:
    print("Connection error:", e)
