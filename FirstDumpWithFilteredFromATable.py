"""
Created By Shashi Preetham
"""
import csv
import gzip
import os
import tempfile
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
import psycopg2
from pathlib import Path

"""Gets 500 rows from the query and sends it in batch wise(i.e, 100 rows after another 100 rows)"""
batch_size = 100
file_split_size = 500

"""Step-1: Connect to the DB """
conn = psycopg2.connect("host=********* "
                        "dbname=********* "
                        "user=********* "
                        "password='*********'")
cur = conn.cursor()
conn.commit()

"""Step-2: Get the number of things from DB """
cur.execute("Select Distinct source_id from value_stream;")
data = cur.fetchall();
print(data)

""" Function that appends the data to the Blobs in Container """


def load_to_azure2(filename, sourceid):
    flag = False
    blob_service_client = BlobServiceClient.from_connection_string(
        "DefaultEndpointsProtocol=https;AccountName=*********;AccountKey=*********;EndpointSuffix=core.windows.net")
    service_client = DataLakeServiceClient(
        account_url="{}://{}.dfs.core.windows.net".format("https", "*********"),
        credential="*********")
    file_system_client = service_client.get_file_system_client(file_system="*********")
    # Get the Blob Names from the Container
    container_client = blob_service_client.get_container_client("*********")
    blobs_list = container_client.list_blobs()
    # Check the Blob name is present or not
    for blob in blobs_list:
        if blob.name == sourceid + ".csv":
            flag = True
            break
    if flag:
        file_client = file_system_client.get_file_client(sourceid + ".csv")
        file_client.get_file_properties().size
        filesize_previous = file_client.get_file_properties().size
        local_file = gzip.open(filename, 'r')  # Change the Path over here !!!
        file_contents = local_file.read()
        file_client.append_data(data=file_contents, offset=filesize_previous, length=len(file_contents))
        file_client.flush_data(filesize_previous + len(file_contents))
    else:
        file_client = file_system_client.create_file(sourceid + ".csv")
        local_file = gzip.open(filename, 'r')  # Change the Path over here !!!
        file_contents = local_file.read()
        file_client.append_data(data=file_contents, offset=0, length=len(file_contents))
        file_client.flush_data(len(file_contents))


""" Step-3: Get the data from DB and Send the data to coud in batch wise """

for x in data:
    thingname = x[0]
    query = ("Select source_id,time,property_name,property_value From public.value_stream where source_id like '" + thingname + "' order by time Limit 1000")
    cur.execute(query)
    print("Query Executed for " + thingname)

    with tempfile.TemporaryDirectory() as td:
        temp_file_name = Path(td, 'tmpfile').as_posix()
        batch_count = 0
        file_count = 0
        is_finished = False
        while not is_finished:
            with gzip.open(temp_file_name, "wt") as f:
                file_count += 1
                rows_written = 0
                writer = csv.writer(
                    f, dialect="unix", delimiter=",", quoting=csv.QUOTE_MINIMAL
                )
                while True:
                    batch_count += 1
                    print(f"fetching rows: batch {batch_count}")
                    rows = cur.fetchmany(batch_size)
                    if rows:
                        writer.writerows(rows)
                        rows_written += batch_size
                    else:
                        is_finished = True
                        break
                    if rows_written >= file_split_size:
                        break
            if rows_written > 0:
                load_to_azure2(filename=temp_file_name, sourceid=thingname)
                print("file uploaded")
                os.remove(temp_file_name)
            else:
                print("no rows written. skipping upload.")
                break