import typing
import json

from DbType import DbType

class ConfigFileBuilder:

    @staticmethod
    def generate(
        outputPath: str, 
        plugins: typing.List[str], 
        storagePath: str, 
        dbType: DbType, 
        dbSize: str,
        port: int
        ):

        config = {}
        config["Plugins"] = plugins
        config["StorageDirectory"] = storagePath
        
        dbConfig = {}
        dbConfig["EnableIndex"] = True
        dbConfig["Host"] = "127.0.0.1"
        dbConfig["Lock"] = False
        dbConfig["Port"] = port

        if dbType == DbType.MySQL:
            dbConfig["EnableStorage"] = False
            dbConfig["Database"] = "orthanc"
            dbConfig["Username"] = "orthanc"
            dbConfig["Password"] = "orthanc"

            config["MySQL"] = dbConfig

        elif dbType == DbType.PG9 or dbType == DbType.PG10:
            dbConfig["EnableStorage"] = False
            dbConfig["Database"] = "orthanc"
            dbConfig["Username"] = "orthanc"
            dbConfig["Password"] = "orthanc"

            config["PostgreSQL"] = dbConfig

        elif dbType == DbType.MSSQL:
            dbConfig["ConnectionString"] = "Driver={ODBC Driver 13 for SQL Server};Server=tcp:index," + port + ";Database=master;Uid=sa;Pwd=MyStrOngPa55word!;Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=30"
            dbConfig["LicenseString"] = "1abaamBcReVXv6EtE_X___demo-orthanc%osimis.io___HHHnqVHYvEkR3jGs2Y3EvpbxZgTt7yaCniJa2Bz7hFWTMa" # note: this is a trial license expiring on 2018-09-30, replace with your license code

            config["MSSQL"] = dbConfig

        elif DbType == DbType.Sqlite:
            config["IndexDirectory"] = storagePath

        else:
            raise NotImplementedError

        with open(outputPath, "w") as configFile:
           json.dump(config, fp=configFile, indent=4)