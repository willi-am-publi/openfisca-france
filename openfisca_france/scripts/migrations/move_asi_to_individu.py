# -*- coding: utf-8 -*-

import yaml
import yamlordereddictloader
import sys
import pprint

filename = 'test_mes_aides_54d4e0704ec19fce442273a0.yaml'

def migrateTestFile(path):
	with open(path, 'r') as f:
		data = yaml.load(f, Loader=yamlordereddictloader.Loader)

	with open(path, 'w') as f:
		yaml.dump(data, f, default_flow_style=False, allow_unicode=True, Dumper=yamlordereddictloader.SafeDumper)


if __name__ == "__main__":
	for p in sys.argv[1:]:
		migrateTestFile(p)
