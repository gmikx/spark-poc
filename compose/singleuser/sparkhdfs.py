"""Pomocnik HDFS dla notebooków i skryptów: klient WebHDFS z właściwym adresem i użytkownikiem.

    import sparkhdfs
    fs = sparkhdfs.client()
    fs.upload("dane.csv", "plik_lokalny.csv")        # do /user/<login>/dane.csv
    fs.download("wynik.parquet", "wynik_lokalny", n_threads=1)
    fs.list(".")
"""
import getpass
import os

from hdfs import InsecureClient


def client():
    user = os.environ.get("HADOOP_USER_NAME") or getpass.getuser()
    return InsecureClient(os.environ.get("HDFS_WEBHDFS", "http://namenode:9870"), user=user, root=f"/user/{user}")
