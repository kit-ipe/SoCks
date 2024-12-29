# SoCks (SoC Blocks)

## Installation

It is recommended to install SoCks in a python environment. You can create a new one with the following command:
```
$ python3.10 -m venv ~/py_envs/socks
```

In the python environment run:
```
$ cd <THIS REPO>/tool
$ pip install -U .
```

For a development installation do the following instead:
```
$ cd <THIS REPO>/tool
$ pip install -e .
```

## Quick start

This section assumes that you already have a SoCks project. To be able to use the SoCks command you have to be
in a SoCks project directory (A directory that contains at least `project.yml`).
In such a directory you can run the following command to build the full image:
```
$ socks all build
```
It is also possible to build individual blocks with:
```
$ socks <BLOCK> build
```
If you need further assistance you can put `--help` behind every sub-command. E.g. like this
```
$ socks --help
$ socks fsbl --help
```
SoCks supports tab completion, but you have to enable it manually in every new shell with the following command:
```
$ eval "$(register-python-argcomplete socks)"
```

## What is SoCks?

SoCks (short for SoC blocks) is a lightweight and modular framework to build complete embedded Linux images for SoC devices. Currently, it supports only AMD Xilinx ZynqMP devices, but it is planned to add support for AMD Xilinx Versal devices in the future.