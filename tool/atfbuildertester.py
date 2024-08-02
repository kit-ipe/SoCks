#!/usr/bin/env python3

import atfbuilder
import subprocess

atfbuilder = atfbuilder.ATFBuilder(socks_dir='/home/marvin/Projects/Build_System_Tests/SoCks/tool/', project_dir='/home/marvin/Projects/Build_System_Tests/SoCks/project/') # Mount paths must be absolute

#atfbuilder.init_repo()
#atfbuilder.apply_patches()
atfbuilder.start_container()