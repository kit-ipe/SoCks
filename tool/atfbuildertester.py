#!/usr/bin/env python3

import atfbuilder
import subprocess

atfbuilder = atfbuilder.ATFBuilder(socks_dir='.', project_dir='./../project/')

#atfbuilder.init_repo()
#atfbuilder.apply_patches()
atfbuilder.clean_container_image()