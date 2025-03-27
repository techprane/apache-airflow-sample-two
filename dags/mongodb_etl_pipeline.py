# mongodb_etl_pipeline.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
import logging
import os
import ssl

# Load environment variables from .env file
load_dotenv()

# Get MONGO_URI from environment or raise error if not set
MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    raise ValueError(
        "MONGO_URI is not set. Please define it in your environment or .env file.")

logging.info("MONGO_URI loaded successfully.")

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'mongodb_etl_pipeline',
    default_args=default_args,
    description='A simple ETL pipeline using MongoDB Atlas with Apache Airflow',
    schedule_interval='@daily',
    catchup=False,
)

SOURCE_COLLECTION = "source_collection"
DEST_COLLECTION = "dest_collection"


def extract_data(**context):
    logging.info("Starting extraction...")
    client = None
    try:
        client = MongoClient(
            MONGO_URI,
            tls=True,
            tlsAllowInvalidCertificates=True,  # Only for testing; remove in production!
            serverSelectionTimeoutMS=30000
        )
        db = client["airflow_db"]
        source_data = list(db[SOURCE_COLLECTION].find({}))
        # Convert ObjectId fields to strings to make them JSON serializable
        for doc in source_data:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        logging.info(
            f"Extracted {len(source_data)} records from {SOURCE_COLLECTION}.")
        context['ti'].xcom_push(key='raw_data', value=source_data)
    except Exception as e:
        logging.exception("Extraction failed:")
        raise
    finally:
        if client:
            client.close()


def transform_data(**context):
    logging.info("Starting transformation...")
    try:
        ti = context['ti']
        raw_data = ti.xcom_pull(key='raw_data', task_ids='extract_task')
        if raw_data is None:
            raise ValueError("No data received from extract_task.")
        transformed_data = []
        for record in raw_data:
            record['processed'] = True
            # Optionally remove _id if you don't need it later:
            record.pop('_id', None)
            transformed_data.append(record)
        logging.info(f"Transformed {len(transformed_data)} records.")
        ti.xcom_push(key='transformed_data', value=transformed_data)
    except Exception as e:
        logging.exception("Transformation failed:")
        raise


def load_data(**context):
    logging.info("Starting load...")
    client = None
    try:
        ti = context['ti']
        transformed_data = ti.xcom_pull(
            key='transformed_data', task_ids='transform_task')
        if transformed_data is None:
            raise ValueError("No data received from transform_task.")
        client = MongoClient(
            MONGO_URI,
            tls=True,
            tlsAllowInvalidCertificates=True,  # Only for testing; remove in production!
            serverSelectionTimeoutMS=30000
        )
        db = client["airflow_db"]
        if transformed_data:
            result = db[DEST_COLLECTION].insert_many(transformed_data)
            logging.info(
                f"Loaded {len(result.inserted_ids)} records into {DEST_COLLECTION}.")
        else:
            logging.info("No data to load.")
    except Exception as e:
        logging.exception("Loading failed:")
        raise
    finally:
        if client:
            client.close()


extract_task = PythonOperator(
    task_id='extract_task',
    python_callable=extract_data,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_task',
    python_callable=transform_data,
    dag=dag,
)

load_task = PythonOperator(
    task_id='load_task',
    python_callable=load_data,
    dag=dag,
)

extract_task >> transform_task >> load_task
