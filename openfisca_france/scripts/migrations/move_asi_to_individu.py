# -*- coding: utf-8 -*-

import sys
import pprint
import io
from ruamel.yaml import YAML

yaml = YAML()
yaml.default_flow_style = False

def migrateTestFile(path):
    with io.open(path, 'r', encoding='utf8') as f:
        data = yaml.load(f)

    with io.open(path, 'w', encoding='utf8') as f:
        yaml.dump(data, f)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        migrateTestFile(p)
