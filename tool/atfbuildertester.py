#!/usr/bin/env python3

import atfbuilder
import subprocess

atfbuilder = atfbuilder.ATFBuilder(project_dir='../project/')

atfbuilder.init_repo()
atfbuilder.apply_patches()