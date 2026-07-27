from BeadArrayFiles.module import ClusterFile

if __name__ == "__main__":
    path = r"C:\Users\Bernhard\PycharmProjects\CNVMaster\product\executable\example_data\static-data\ExampleArray\GSAMD-24v3-0-EA_20034606_A1.egt"
    handle = open(path, "rb")

    meta_and_data = ClusterFile.read_cluster_file(handle)
    print("meta_and_data", list(meta_and_data.name2cluster_record.keys())[0], list(meta_and_data.name2cluster_record.values())[0].get)