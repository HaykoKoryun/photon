#!/bin/bash
#################################################
#       Title:  mk-setup-grub                   #
#        Date:  2014-11-26                      #
#     Version:  1.0                             #
#      Author:  sharathg@vmware.com             #
#     Options:                                  #
#################################################
#    Overview
#        This is a precursor for the vmware build system.
#        This assumes that an empty hard disk is attached to the build VM.
#        The path to this empty disk is specified in the HDD variable in config.inc
#    End
#

grub_efi_install()
{
	cp -r $SCRIPT_PATH/esp/ls1012afrwy_boot.scr $BUILDROOT/boot/esp/
	cp -r $SCRIPT_PATH/esp/ls1046afrwy_boot.scr $BUILDROOT/boot/esp/
	mkdir -p $BUILDROOT/boot/esp/EFI/BOOT/
        cp $INSTALLER_PATH/EFI_aarch64/BOOT/bootaa64.efi $BUILDROOT/boot/esp/EFI/BOOT/
}


set -o errexit        # exit if error...insurance ;)
set -o nounset        # exit if variable not initalized
set +h            # disable hashall
PRGNAME=${0##*/}    # script name minus the path
SCRIPT_PATH=$(dirname $(realpath -s $0))
INSTALLER_PATH=$SCRIPT_PATH/../../../installer
source ${INSTALLER_PATH}/config.inc             #       configuration parameters
source ${INSTALLER_PATH}/function.inc #    commonn functions
LOGFILE=/var/log/"${PRGNAME}-${LOGFILE}"    #    set log file name
ARCH=$(uname -m)    # host architecture
[ ${EUID} -eq 0 ]    || fail "${PRGNAME}: Need to be root user: FAILURE"
> ${LOGFILE}        #    clear/initialize logfile

# Check if passing a HHD and partition
if [ $# -eq 6 ] ; then
    BOOTMODE=$1
    HDD=$2
    ROOT_PARTITION_PATH=$3
    BOOT_PARTITION_PATH=$4
    BOOT_DIRECTORY=$5
    BOOT_PARTITION_NUMBER=$6
fi


#
#    Install grub2.
#
BOOT_UUID=$(blkid -s UUID -o value $ROOT_PARTITION_PATH)

echo "$ROOT_PARTITION_PATH"
echo "$BUILDROOT"

mkdir -p $BUILDROOT/boot/grub2/
ln -sfv grub2 $BUILDROOT/boot/grub

grub_efi_install


EXTRA_PARAMS="rootwait rw console=ttyS0,115200n8 console=tty0 rootfs=/dev/mmcblk0p2"

cat > $BUILDROOT/boot/grub2/grub.cfg << EOF
# Begin /boot/grub2/grub.cfg

set default=0
set timeout=2
loadfont ${BOOT_DIRECTORY}grub2/ascii.pf2

insmod all_video
insmod gfxterm
insmod png
insmod ext2

set theme=${BOOT_DIRECTORY}grub2/themes/photon/theme.txt
load_env -f ${BOOT_DIRECTORY}photon.cfg
if [ -f  ${BOOT_DIRECTORY}systemd.cfg ]; then
    load_env -f ${BOOT_DIRECTORY}systemd.cfg
else
    set systemd_cmdline=net.ifnames=0
fi
set rootpartition=/dev/mmcblk0p2

menuentry "Photon" {
    linux ${BOOT_DIRECTORY}\$photon_linux root=\$rootpartition \$photon_cmdline \$systemd_cmdline $EXTRA_PARAMS
    if [ -f ${BOOT_DIRECTORY}\$photon_initrd ]; then
        initrd ${BOOT_DIRECTORY}\$photon_initrd
    fi
}
# End /boot/grub2/grub.cfg
EOF



#mkdir $BUILDROOT/boot/grub
#cp -rfa $BUILDROOT/boot/grub2/* $BUILDROOT/boot/grub/

#grub_efi_install

#Cleanup the workspace directory
rm -rf "$BUILDROOT"/tools
rm -rf "$BUILDROOT"/RPMS

