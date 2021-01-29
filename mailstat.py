import argparse
import datetime
import os.path
import re

import pyhocon

MAILSTAT_CONFIG = "~/.mailstat"

ISO_8601_DATE_FORMAT = "%Y-%m-%d"
ISO_8601_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)

def parse_date(date):
    return datetime.datetime.strptime(date, ISO_8601_DATE_FORMAT).date()

def parse_search(search):
    search = search.split()
    for i, search_key in enumerate(search):
        if ISO_8601_DATE_PATTERN.fullmatch(search_key):
            search[i] = parse_date(search_key)
    return search

def imap_source(source):
    import imapclient
    client = imapclient.IMAPClient(source["host"])
    client.login(source["username"], source["password"])
    client.select_folder(source["folder"])
    messages = client.search(parse_search(source["search"]))
    return len(messages)

source_registry = {
    "imap": imap_source,
}

def format_influxdb(result):
    lines = []
    for name in result:
        value = result[name]
        line = f"mail,account={name} count={value}i"
        lines.append(line)
    return "\n".join(lines)

def influxdb_target(target, result):
    from influxdb_client import InfluxDBClient
    from influxdb_client.client.write_api import SYNCHRONOUS
    client = InfluxDBClient(target["url"], target["token"])
    write_api = client.write_api(SYNCHRONOUS)
    write_api.write(target["bucket"], target["org"], format_influxdb(result))

def format_stdout(result):
    lines = []
    for name in result:
        value = result[name]
        line = f"{name} {value}"
        lines.append(line)
    return "\n".join(lines)

def stdout_target(target, result):
    print(format_stdout(result))

target_registry = {
    "influxdb": influxdb_target,
    "stdout": stdout_target,
}

def process_sources(sources):
    result = {}
    for source in sources:
        name = source["name"]
        type = source["type"]
        process_source = source_registry[type]
        value = process_source(source)
        result[name] = value
    return result

def process_targets(targets, result):
    for target in targets:
        type = target["type"]
        process_target = target_registry[type]
        process_target(target, result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", metavar="ACCOUNT")
    args = parser.parse_args()
    config_path = os.path.expanduser(MAILSTAT_CONFIG)
    config = pyhocon.ConfigFactory.parse_file(config_path)
    if args.test:
        sources = [source for source in config["sources"]
                   if source["name"] == args.test]
        targets = [{"type": "stdout"}]
    else:
        sources = config["sources"]
        targets = config["targets"]
    result = process_sources(sources)
    process_targets(targets, result)
