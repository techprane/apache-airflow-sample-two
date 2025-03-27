# mongodb_etl_pipeline.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
import logging
import os

# Load environment variables from .env file
load_dotenv()

# Use a default MONGO_URI if none is provided (for local testing)
MONGO_URI = os.getenv(
    'MONGO_URI', 'mongodb+srv://dev:RRMQJhiGu7xbjKOX@mycluster.0elq2.mongodb.net/?retryWrites=true&w=majority&appName=MyCluster')

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG (at module level so Airflow can detect it)
dag = DAG(
    'mongodb_etl_pipeline',
    default_args=default_args,
    description='A simple ETL pipeline using MongoDB Atlas with Apache Airflow',
    schedule_interval='@daily',
    catchup=False,
)

SOURCE_COLLECTION = "source_collection"
DEST_COLLECTION = "dest_collection"


def extract_data(**kwargs):
    logging.info("Starting extraction...")
    try:
        client = MongoClient(MONGO_URI)
        db = client["airflow_db"]
        # Extract all documents from the source collection
        source_data = list(db[SOURCE_COLLECTION].find({}))
        logging.info(
            f"Extracted {len(source_data)} records from {SOURCE_COLLECTION}.")
        # Push the data to XCom for downstream tasks
        kwargs['ti'].xcom_push(key='raw_data', value=source_data)
    except Exception as e:
        logging.error(f"Extraction failed: {e}")
        raise
    finally:
        client.close()


def transform_data(**kwargs):
    logging.info("Starting transformation...")
    try:
        ti = kwargs['ti']
        raw_data = ti.xcom_pull(key='raw_data', task_ids='extract_task')
        transformed_data = []
        for record in raw_data:
            # Example transformation: add a new field and remove _id field
            record['processed'] = True
            record.pop('_id', None)
            transformed_data.append(record)
        logging.info(f"Transformed {len(transformed_data)} records.")
        ti.xcom_push(key='transformed_data', value=transformed_data)
    except Exception as e:
        logging.error(f"Transformation failed: {e}")
        raise


def load_data(**kwargs):
    logging.info("Starting load...")
    try:
        ti = kwargs['ti']
        transformed_data = ti.xcom_pull(
            key='transformed_data', task_ids='transform_task')
        client = MongoClient(MONGO_URI)
        db = client["airflow_db"]
        if transformed_data:
            result = db[DEST_COLLECTION].insert_many(transformed_data)
            logging.info(
                f"Loaded {len(result.inserted_ids)} records into {DEST_COLLECTION}.")
        else:
            logging.info("No data to load.")
    except Exception as e:
        logging.error(f"Loading failed: {e}")
        raise
    finally:
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

# Set task dependencies
extract_task >> transform_task >> load_task
