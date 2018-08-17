import typing
import json
import os

from DbType import DbType

class ConfigFileBuilder:

    @staticmethod
    def generate(
        outputPath: str, 
        pluginsPath: str, 
        storagePath: str, 
        dbType: DbType, 
        dbSize: str,
        port: int
        ):

        config = {}
        config["StorageDirectory"] = storagePath
        
        dbConfig = {}
        dbConfig["EnableIndex"] = True

        if dbType.isServer():
            dbConfig["Host"] = "127.0.0.1"
            dbConfig["Lock"] = False
            dbConfig["Port"] = port

        if dbType == DbType.MySQL:
            config["Plugins"] = [os.path.join(pluginsPath, "libOrthancMySQLIndex.so")]
            dbConfig["EnableStorage"] = False
            # config["Plugins"] = [os.path.join(pluginsPath, "libOrthancMySQLStorage.so")]

            dbConfig["Database"] = "orthanc"
            dbConfig["Username"] = "orthanc"
            dbConfig["Password"] = "orthanc"

            config["MySQL"] = dbConfig

        elif dbType.isPG():
            config["Plugins"] = [os.path.join(pluginsPath, "libOrthancPostgreSQLIndex.so")]
            dbConfig["EnableStorage"] = False
            # config["Plugins"] = [os.path.join(pluginsPath, "libOrthancPostgreSQLStorage.so")]

            dbConfig["Database"] = "postgres"
            dbConfig["Username"] = "postgres"

            config["PostgreSQL"] = dbConfig

        elif dbType == DbType.MSSQL:
            config["Plugins"] = [os.path.join(pluginsPath, "libOrthancMsSqlIndex.so")]
            dbConfig["EnableStorage"] = False

            dbConfig["ConnectionString"] = "Driver={ODBC Driver 13 for SQL Server};Server=tcp:127.0.0.1," + str(port) + ";Database=master;Uid=sa;Pwd=MyStrOngPa55word!;Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=30"
            dbConfig["LicenseString"] = "1abaamBcReVXv6EtE_X___demo-orthanc%osimis.io___HHHnqVHYvEkR3jGs2Y3EvpbxZgTt7yaCniJa2Bz7hFWTMa" # note: this is a trial license expiring on 2018-09-30, replace with your license code

            config["MSSQL"] = dbConfig

        elif dbType.isSqlite():
            config["IndexDirectory"] = storagePath
            if dbType == DbType.SqlitePlugin:
                config["Plugins"] = [os.path.join(pluginsPath, "libOrthancSQLiteIndex.so")]

        else:
            raise NotImplementedError

        with open(outputPath, "w") as configFile:
           json.dump(config, fp=configFile, indent=4)