import argparse
from ConfigFileBuilder import ConfigFileBuilder
from TestConfig import TestConfig
from DbServer import DbServer
from DbType import DbType
from DbSize import DbSize

testConfigs = {
    "mysql-small" : TestConfig(label= "mysql-small", dbSize=DbSize.Small, dbServer=DbServer(dbType=DbType.MySQL, port=2000)),
    "pg9-small": TestConfig(label= "pg9-small", dbSize=DbSize.Small, dbServer=DbServer(dbType=DbType.PG9, port=2001)),
    "pg10-small": TestConfig(label= "pg10-small", dbSize=DbSize.Small, dbServer=DbServer(dbType=DbType.PG10, port=2002)),
    "pg11-small": TestConfig(label= "pg11-small", dbSize=DbSize.Small, dbServer=DbServer(dbType=DbType.PG11, port=2003)),
    "mssql-small" : TestConfig(label= "mssql-small", dbSize=DbSize.Small, dbServer=DbServer(dbType=DbType.MSSQL, port=2004)),
    "sqlite-small": TestConfig(label= "sqlite-small", dbSize=DbSize.Small, dbType=DbType.Sqlite),
    "sqliteplugin-small": TestConfig(label= "sqliteplugin-small", dbSize=DbSize.Small, dbType=DbType.SqlitePlugin),

    "mysql-tiny" : TestConfig(label= "mysql-tiny", dbSize=DbSize.Tiny, dbServer=DbServer(dbType=DbType.MySQL, port=3000)),
    "pg9-tiny": TestConfig(label= "pg9-tiny", dbSize=DbSize.Tiny, dbServer=DbServer(dbType=DbType.PG9, port=3001)),
    "pg10-tiny": TestConfig(label= "pg10-tiny", dbSize=DbSize.Tiny, dbServer=DbServer(dbType=DbType.PG10, port=3002)),
    "pg11-tiny": TestConfig(label= "pg11-tiny", dbSize=DbSize.Tiny, dbServer=DbServer(dbType=DbType.PG11, port=3003)),
    "mssql-tiny" : TestConfig(label= "mssql-tiny", dbSize=DbSize.Tiny, dbServer=DbServer(dbType=DbType.MSSQL, port=3004)),
    "sqlite-tiny": TestConfig(label= "sqlite-tiny", dbSize=DbSize.Tiny, dbType=DbType.Sqlite),
    "sqliteplugin-tiny": TestConfig(label= "sqliteplugin-tiny", dbSize=DbSize.Tiny, dbType=DbType.SqlitePlugin),

    "mysql-medium" : TestConfig(label= "mysql-medium", dbSize=DbSize.Medium, dbServer=DbServer(dbType=DbType.MySQL, port=4000)),
    "pg9-medium": TestConfig(label= "pg9-medium", dbSize=DbSize.Medium, dbServer=DbServer(dbType=DbType.PG9, port=4001)),
    "pg10-medium": TestConfig(label= "pg10-medium", dbSize=DbSize.Medium, dbServer=DbServer(dbType=DbType.PG10, port=4002)),
    "pg11-medium": TestConfig(label= "pg11-medium", dbSize=DbSize.Medium, dbServer=DbServer(dbType=DbType.PG11, port=4003)),
    "mssql-medium" : TestConfig(label= "mssql-medium", dbSize=DbSize.Medium, dbServer=DbServer(dbType=DbType.MSSQL, port=4004)),
    "sqlite-medium": TestConfig(label= "sqlite-medium", dbSize=DbSize.Medium, dbType=DbType.Sqlite),
    "sqliteplugin-medium": TestConfig(label= "sqliteplugin-medium", dbSize=DbSize.Medium, dbType=DbType.SqlitePlugin),
}

selectedTestConfigs = []

parser = argparse.ArgumentParser(description = "Initializes/Runs/Clears PerfsDb setup.")

# create a cli option for each config
for testConfigName in testConfigs.keys():
    parser.add_argument("--" + testConfigName, action = "store_true")

parser.add_argument("--init", help = "initializes DBs", action = "store_true")
parser.add_argument("--run", help = "runs tests", action = "store_true")
parser.add_argument("--clear", help = "clear DBs", action = "store_true")

parser.add_argument("--orthanc-path", help = "path to the folder containing Orthanc executable", default=".")
parser.add_argument("--plugins-path", help = "path to the folder containing Orthanc executable", default=".")
parser.add_argument("--repeat", help = "number of times to repeat each test to average timings", type=int, default=50)

args = parser.parse_args()

for testConfigName in testConfigs.keys():
    if args.__dict__[testConfigName.replace("-", "_")]:
        selectedTestConfigs.append(testConfigName)

# if no test config specified, take them all
if len(selectedTestConfigs) == 0:
    selectedTestConfigs = testConfigs.keys()

selectedTestConfigs = sorted(selectedTestConfigs)

# if no action specified, it means only run
if not (args.init | args.run | args.clear):
    args.init = False
    args.run = True
    args.clear = False

print("***** Orthanc *******")
print("path    :", args.orthanc_path)

results = {}

for configName in selectedTestConfigs:
    testConfig = testConfigs[configName]
    testConfig.setName(configName)
    testConfig.setRepeatCount(args.repeat)
    
    print("======= " + configName + " ========")

    if args.clear:
        print("** Clearing Db")
        testConfig.clearDb()

    if args.init or args.run:
        print("** Generating config files")
        testConfig.generateOrthancConfigurationFile(args.plugins_path)

        print("** Launching DbServer")
        testConfig.launchDbServer()
        
        print("** Launching Orthanc")
        orthancWasAlreadyRunning = not testConfig.launchOrthanc(args.orthanc_path)
        if orthancWasAlreadyRunning and len(selectedTestConfigs) > 1:
            print("Error: Can't execute multiple configuration on already running Orthanc.  Exit Orthanc and let this script start Orthanc instances")
            exit(-1)

    if args.init:
        testConfig.initializeDb()

    if args.run:
        print("** Runnnig tests")
        results[configName] = testConfig.runTests()
    
    print("** Stopping Orthanc")
    testConfig.stopOrthanc()
    
print("++++++++++++++ results summary +++++++++++++++")
testNames = set()
resultsByTestName = {}
for configName, configResult in results.items():
    for result in configResult:
        testNames.add(result.name)
        if not result.name in resultsByTestName:
            resultsByTestName[result.name] = {}
        resultsByTestName[result.name][configName] = result

headerLine = "{empty:<40}|".format(empty="")
for configName in selectedTestConfigs:
    headerLine += "{configName:^15}|".format(configName=configName)

print(headerLine)

for testName in sorted(testNames):
    resultLine = "{name:<40}|".format(name=testName)
    for configName in selectedTestConfigs:
        resultLine += "{avg:>11.2f} ms |".format(avg = resultsByTestName[testName][configName].averageTimeInMs)
    print(resultLine)

print("** Done")
