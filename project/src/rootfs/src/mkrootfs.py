################################################################################
##        Script based on original script written by Matthias Wittgen         ##
################################################################################
#                                                                              #
# Info:                                                                        #
# - This script is designed to be executed on a platform that can run ARM      #
#   commands (For example a suitable docker container). The qemu integration   #
#   is removed.                                                                #
#                                                                              #
################################################################################

import os
import sys
import subprocess
import logging
import argparse
import errno
import crypt
import augeas

# Get directory (absolute path)  and filename of mkrootfs.py
dirname, filename = os.path.split(os.path.abspath(__file__))

# Set path of the DNF config (lists repos that can be used by DNF)
dnf_conf=dirname+'/dnf.conf'
print("DNF config path: " + dnf_conf)

# Function for running shell command
def run_cmd(command):
    print(command)
    try:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,shell=False)
        while process.poll() is None:
            output = process.stdout.readline()
            if output:
                print(output.strip().decode('utf-8'))
    except:
        raise

# Function for running a DNF command
def run_dnf(rootfs_dir, releasever, command, packages):
    repos="appstream,appstream-source,baseos,baseos-source,extras,extras-source,plus,powertools,ha,ipbus-sw-base,ipbus-sw-updates,smash"
    cmd=["dnf", "-y", "--nodocs", "-c", dnf_conf, "--releasever="+releasever, "--forcearch="+arch, "--repo="+repos+epel, "--verbose", "--installroot="+rootfs_dir, command] + packages
    run_cmd(cmd)

# Set up parser
parser = argparse.ArgumentParser(description='Tool to cross-install a root filesystem for Alma Linux ARM')
FORMAT = '%(levelname)s : %(message)s'
parser.add_argument('-v', '--verbose',      action='store_true',    help='verbose output')
parser.add_argument('-r', '--root',         nargs=1,                help='directory of new rootfs')
parser.add_argument('-a', '--arch',         nargs=1,                help='architecture of target')
parser.add_argument('-e', '--extra',        nargs=1,                help='file with a list of extra packages to be installed')
parser.add_argument('-rv','--releasever',   nargs=1,                help='release version of the OS. Default is 8.7')

# Check which arguments were parsed to the script, store information and inform the user
args = vars(parser.parse_args())
if args['verbose']:
    logging.basicConfig(format=FORMAT,stream=sys.stdout, level=logging.DEBUG)
if args['root'] is not None:
    rootdir=args['root'][0]
    print ("Root directory path: " + rootdir)
else:
    print("Use --root=<dir> to set new rootfs directory")
    exit(-1)
if args['arch'] is not None:
    arch=args['arch'][0]
    print("Building for " + arch)
else:
    print("Use --arch=<arch> to specify build architecture")
    exit(-1)
if arch not in ["armv7hl","aarch64"]:
   print("Invalid CPU architecture")
   exit(-1)
if args['extra'] is not None:
	extra_pkgs_file = open(args['extra'][0],"r")
	extra_pkgs=[]
	for x in extra_pkgs_file:
		x=x.replace("\n", "")
		extra_pkgs.append(x)
	extra_pkgs_file.close()
if args['releasever'] is not None:
    rv=args['releasever'][0]
    print("Building AlmaLinux release version " + rv)
else:
    rv="8.7"
    print("Building default AlmaLinux release version " + rv)	

# Check if script is being ran with sudo (superuser priveleges)
if(os.getuid()!=0):
    print ("Program must to run as superuser")
    print ("Relaunching as: sudo "," ".join(sys.argv))
    os.execvp("sudo", ["sudo", "PATH="+os.getenv("PATH"), "LD_LIBRARY_PATH="+os.getenv("LD_LIBRARY_PATH"), "PYTHONPATH="+os.getenv("PYTHONPATH")] + sys.argv)
    exit(0)

# Set architecture dependent options
if arch == "aarch64":
    epel=",epel,epel-testing"
elif arch == "armv7hl":
    epel=",arm-epel"

# Build the base rootfs
run_dnf(rootdir,rv,"clean",["all"])    # Clean all cache files generated from repository metadata
run_dnf(rootdir,rv,"update",[" "])     # Update all the installed packages
print ("\nRunning dnf group install...\n")
run_dnf(rootdir,rv,"groupinstall",["Minimal Install","--with-optional"])    # The 'Minimal Install' group consists of the 'Core' group and optionally the 'Standard' and 'Guest Agents' groups

# Remove packages that we do not need
print ("\nRemoving unneeded packages...\n")
run_dnf(rootdir,rv,"remove",["iw*firmware*","--setopt=tsflags=noscripts"])
run_dnf(rootdir,rv,"autoremove",[" "])

# Enable additional repos
print ("\nEnabling additional repos...\n")
epel_key_source="https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-8"
epel_key_path="/etc/pki/rpm-gpg/"
if not os.path.exists(epel_key_path+"RPM-GPG-KEY-EPEL-8"):
    print ("EPEL key not found. EPEL needs to be enabled in the host system ('dnf install epel-release')")
    raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), epel_key_path+"RPM-GPG-KEY-EPEL-8")
run_cmd(["wget", epel_key_source, "-P", rootdir+epel_key_path])    # Install EPEL key in rootfs


# Installing user defined packages
if args['extra'] is not None:
	print("\nInstalling user defined packages...\n")
	run_dnf(rootdir,rv,"install",extra_pkgs)

# Configuration using Augeas
rootpwd=crypt.crypt("alma", crypt.mksalt(crypt.METHOD_SHA512))  # Create a root password
aug=augeas.Augeas(root=rootdir)                                 # Create augeas tree
aug.set("/files/etc/shadow/root/password",rootpwd)              # Set password
aug.set("/files/etc/sysconfig/selinux/SELINUX","disabled")      # Disable SELINUX
aug.save()
aug.close()
