# insert_sample_data.py

from pymongo import MongoClient, errors
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    logging.error(
        "MONGO_URI environment variable is not set. Please check your .env file.")
    exit(1)

try:
    # Connect to MongoDB
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=30000)
    db = client["airflow_db"]
    source_collection = db["source_collection"]

    # Sample data to insert
    sample_data = [
        {"name": "Product A", "price": 10, "category": "Food"},
        {"name": "Product B", "price": 20, "category": "Beverage"},
        {"name": "Product C", "price": 15, "category": "Snack"}
    ]

    # Insert sample data
    result = source_collection.insert_many(sample_data)
    logging.info(
        f"Sample data inserted into source_collection. Inserted IDs: {result.inserted_ids}")

except errors.PyMongoError as e:
    logging.error(f"An error occurred while inserting sample data: {e}")
finally:
    client.close()
