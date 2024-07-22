#!/usr/bin/env python3

from jsonschema import validate
import json
import yaml

schema = json.load(open('zynqmp.schema.json', 'r'))

project_config = yaml.safe_load(open('../project/project.tpl.yml', 'r'))

validate(project_config, schema)

#validate([2, 3, 4], {"maxItems": 2})
