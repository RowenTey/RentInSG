import os
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.python import PythonOperator
from datetime import datetime

from docker.types import Mount

DATE_STR = datetime.today().strftime("%Y-%m-%d")
DOCKER_IMAGE = "rowentey/fyp-rent-in-sg:ohmyhome-scraper-latest"
DOCKER_TARGET_VOLUME = "scraper_data"
DOCKER_VOLUME_DIR = "/app/pkg/rental_prices/ohmyhome"
S3_BUCKET = os.environ['S3_BUCKET']
S3_KEY = f"airflow/ohmyhome/{DATE_STR}.parquet.gzip"

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 7, 14),
    'email': ['kaiseong02@gmail.com'],
    'email_on_failure': True,
    'retries': 1
}

dag = DAG(
    'ohmyhome_etl',
    default_args=default_args,
    catchup=False,
    description='A DAG to scrape data from Oh My Home and upload to S3',
    schedule_interval='0 12 * * *',
)


def fetch_csv_from_volume(**kwargs):
    """
    Fetches the content of a CSV file from a Docker container volume.

    Args:
        **kwargs: Additional keyword arguments.

    Returns:
        str: The content of the CSV file.

    Raises:
        None.

    This function uses the `docker` library to create a Docker client and run a container. It retrieves the content of a CSV file
    located in the `/app/output/{DATE_STR}.csv` path within the container. The `DATE_STR` variable is expected to be defined
    elsewhere in the code. The container is configured with the `DOCKER_TARGET_VOLUME` volume, which is mounted in read-only mode.
    The container is removed after the content is retrieved.

    Note:
        - The `docker` library is required and must be installed.
        - The `DATE_STR` variable must be defined and contain a valid date string.
    """
    from docker import from_env

    client = from_env()
    container = client.containers.run(
        'alpine',
        f'cat {DOCKER_VOLUME_DIR}/{DATE_STR}.csv',
        volumes={DOCKER_TARGET_VOLUME: {'bind': DOCKER_VOLUME_DIR, 'mode': 'ro'}},
        remove=True
    )

    csv_content = container.decode('utf-8')
    return csv_content


def convert_csv_to_df(**kwargs):
    import pandas as pd
    from io import StringIO

    ti = kwargs['ti']
    csv_content = ti.xcom_pull(task_ids='fetch_csv')

    df = pd.read_csv(StringIO(csv_content))
    return df


def upload_to_s3(s3_bucket, s3_key, **kwargs):
    """
    Uploads a local file to an S3 bucket.

    Args:
        s3_bucket (str): The name of the S3 bucket.
        s3_key (str): The key of the file in the S3 bucket.
        **kwargs: Additional keyword arguments.

    Returns:
        None

    Raises:
        None

    This function uploads a local file to an S3 bucket using the provided S3 bucket and key.
    The local file path is obtained from the TaskInstance (ti) using the task_ids 'fetch_csv'.
    The function first prints the local file path being uploaded to S3.
    It then uses the S3Hook to load the file into the S3 bucket.
    Finally, it prints a message indicating that the file has been uploaded to S3.

    Note:
        - For more information on transferring files to and from an S3 bucket using Apache Airflow,
        refer to the blog post at https://blog.devgenius.io/transfer-files-to-and-from-s3-bucket-using-apache-airflow-e3790a3b47a2.
    """
    from lib.utils.parquet import parquet
    from airflow.providers.amazon.aws.operators.s3 import S3Hook

    ti = kwargs['ti']
    df = ti.xcom_pull(task_ids='convert_csv_to_df')

    parquet_bytes = parquet(df)

    hook = S3Hook(aws_conn_id='aws_conn')
    hook.load_file_obj(parquet_bytes, s3_key, bucket_name=s3_bucket, replace=True)

# def clean_and_transform(**kwargs):
#     from lib.transformers.transform import transform

#     ti = kwargs['ti']
#     df = ti.xcom_pull(task_ids='convert_csv_to_df')

#     print(f"Got df! \n{df}\n")
#     transform()

# # Task to push cleaned data to DuckDB as a data sink (example)
# def push_to_duckdb(**kwargs):
#     # Your logic to push data to DuckDB
#     print("Pushing cleaned data to DuckDB")


"""
spark_task = SparkSubmitOperator(
    task_id='clean_and_transform',
    application='/path/to/your/spark_job.py',  # Path to your Spark job script
    name='clean_and_transform_spark_job',
    conn_id='spark_default',  # Airflow connection ID for Spark
    verbose=False,  # Optional, set to True for verbose logging
    application_args=['arg1', 'arg2'],  # Arguments to your Spark job if needed
    dag=dag,
)
"""

docker_task = DockerOperator(
    task_id='scrape_data',
    image=DOCKER_IMAGE,
    api_version='auto',
    auto_remove=True,
    mounts=[
        Mount(source=DOCKER_TARGET_VOLUME, target=DOCKER_VOLUME_DIR, type='volume'),
    ],
    # Specify the Docker daemon socket
    docker_url='unix://var/run/docker.sock',
    retrieve_output=True,
    tty=True,
    force_pull=True,
    environment={
        "LOG_OUTPUT": "false",
        "DEBUG_MODE": "true",
    },
    dag=dag,
)

fetch_csv_task = PythonOperator(
    task_id='fetch_csv',
    python_callable=fetch_csv_from_volume,
    dag=dag,
)

convert_csv_task = PythonOperator(
    task_id='convert_csv_to_df',
    python_callable=convert_csv_to_df,
    dag=dag,
)

upload_to_s3_task = PythonOperator(
    task_id='upload_to_s3',
    python_callable=upload_to_s3,
    op_kwargs={'s3_bucket': S3_BUCKET, 's3_key': S3_KEY},
    dag=dag,
)

# clean_and_transform_task = PythonOperator(
#     task_id='clean_and_transform',
#     python_callable=clean_and_transform,
#     dag=dag,
# )

# push_to_duckdb_task = PythonOperator(
#     task_id='push_to_duckdb',
#     python_callable=push_to_duckdb,
#     dag=dag,
# )

docker_task >> fetch_csv_task
fetch_csv_task >> convert_csv_task
convert_csv_task >> upload_to_s3_task
# convert_csv_task >> [upload_to_s3_task, clean_and_transform_task]
# clean_and_transform_task >> push_to_duckdb_task
