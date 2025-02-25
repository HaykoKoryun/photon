#!/usr/bin/python2
#
#    Copyright (C) 2015 vmware inc.
#
#    Author: Touseef Liaqat <tliaqat@vmware.com>

import subprocess
import os
import re
import glob
import modules.commons
from installer import Installer
from actionresult import ActionResult

class OstreeInstaller(Installer):

    def __init__(self, install_config, maxy = 0, maxx = 0, iso_installer = False, rpm_path = "../stage/RPMS", log_path = "../stage/LOGS", log_level = "info"):
        Installer.__init__(self, install_config, maxy, maxx, iso_installer, rpm_path, log_path, log_level)
        self.repo_config = {}
        self.repo_read_conf()

    def get_ostree_repo_url(self):
        self.default_repo = 'default_repo' in self.install_config and self.install_config['default_repo'];
        if not self.default_repo:
            self.ostree_repo_url = self.install_config['ostree_repo_url']
            self.ostree_ref = self.install_config['ostree_repo_ref']

    def repo_read_conf(self):
        with open("ostree-release-repo.conf") as repo_conf:
            for line in repo_conf:
                name, value = line.partition("=")[::2]
                self.repo_config[name] = value.strip(' \n\t\r')

    def pull_repo(self, repo_url, repo_ref):
        if self.default_repo:
            self.run("ostree remote add --repo={}/ostree/repo --set=gpg-verify=false photon {}".format(self.photon_root, repo_url), "Adding OSTree remote")
            self.run("ostree pull-local --repo={}/ostree/repo {}".format(self.photon_root, self.local_repo_path), "Pulling OSTree repo")
            self.run("mv {}/ostree/repo/refs/heads {}/ostree/repo/refs/remotes/photon".format(self.photon_root, self.photon_root))
            self.run("mkdir -p {}/ostree/repo/refs/heads".format(self.photon_root, self.photon_root))
        else:
            self.run("ostree remote add --repo={}/ostree/repo --set=gpg-verify=false photon {}".format(self.photon_root, repo_url), "Adding OSTree remote")
            self.run("ostree pull --repo={}/ostree/repo photon {}".format(self.photon_root, repo_ref), "Pulling OSTree remote repo")

    def deploy_ostree(self, repo_url, repo_ref):
        self.run("ostree admin --sysroot={} init-fs {}".format(self.photon_root, self.photon_root), "Initializing OSTree filesystem")
        self.pull_repo(repo_url, repo_ref)
        self.run("ostree admin --sysroot={} os-init photon ".format(self.photon_root), "OSTree OS Initializing")
        self.run("ostree admin --sysroot={} deploy --os=photon photon:{}".format(self.photon_root, repo_ref), "Deploying")

    def do_systemd_tmpfiles_commands(self, commit_number):
        prefixes = ["/var/home",
            "/var/roothome",
            "/var/lib/rpm",
            "/var/opt",
            "/var/srv",
            "/var/userlocal",
            "/var/mnt",
            "/var/spool/mail"]

        for prefix in prefixes:
            command = "systemd-tmpfiles --create --boot --root={}/ostree/deploy/photon/deploy/{}.0 --prefix={}".format(self.photon_root, commit_number, prefix)
            self.run(command, "systemd-tmpfiles command done")

    def mount_devices_in_deployment(self, commit_number):
        for command in ["mount -t bind -o bind,defaults /dev  {}/ostree/deploy/photon/deploy/{}.0/dev",
            "mount -t devpts -o gid=5,mode=620 devpts  {}/ostree/deploy/photon/deploy/{}.0/dev/pts",
            "mount -t tmpfs -o defaults tmpfs  {}/ostree/deploy/photon/deploy/{}.0/dev/shm",
            "mount -t proc -o defaults proc  {}/ostree/deploy/photon/deploy/{}.0/proc",
            "mount -t bind -o bind,defaults /run  {}/ostree/deploy/photon/deploy/{}.0/run",
            "mount -t sysfs -o defaults sysfs  {}/ostree/deploy/photon/deploy/{}.0/sys" ]:
            self.run(command.format(self.photon_root, commit_number), "mounting done")

    def get_commit_number(self, ref):
        fileName = os.path.join(self.photon_root, "ostree/repo/refs/remotes/photon/{}".format(ref))
        commit_number = None
        with open (fileName, "r") as file:
            commit_number = file.read().replace('\n', '')
        return commit_number

    def _unsafe_install(self):
        self.org_photon_root = self.photon_root
        sysroot_ostree = os.path.join(self.photon_root, "ostree")
        sysroot_boot = os.path.join(self.photon_root, "boot")
        sysroot_bootefi = os.path.join(self.photon_root, "bootefi")
        loader0 = os.path.join(sysroot_boot, "loader.0")
        loader1 = os.path.join(sysroot_boot, "loader.1")

        boot0 = os.path.join(sysroot_ostree, "boot.0")
        boot1 = os.path.join(sysroot_ostree, "boot.1")

        boot01 = os.path.join(sysroot_ostree, "boot.0.1")
        boot11 = os.path.join(sysroot_ostree, "boot.1.1")

        self.get_ostree_repo_url()

        self.window.show_window()
        self.progress_bar.initialize("Initializing installation...")
        self.progress_bar.show()

        self._execute_modules(modules.commons.PRE_INSTALL)

        disk_partition = self.install_config['disk']['disk']
        if re.search(r'mmcblk', disk_partition):
            disk = disk_partition + "p"
        else:
            disk = disk_partition
        self.run("sgdisk -d 3 -d 2 -d 1 -n 3::+300M -n 2::+8M -n 1::+2M -n 4: -p {}".format(disk_partition), "Updating partition table for OSTree")
        self.run("sgdisk -t1:ef02 {}".format(disk_partition))
        self.run("sgdisk -t2:ef00 {}".format(disk_partition))
        self.run("mkfs -t vfat {}2".format(disk))
        self.run("mkfs -t ext4 {}3".format(disk))
        self.run("mkfs -t ext4 {}4".format(disk))
        self.run("mount {}4 {}".format(disk, self.photon_root))
        self.run("mkdir -p {} ".format(sysroot_boot))
        self.run("mount {}3 {}".format(disk, sysroot_boot))

        self.run("mkdir -p {} ".format(sysroot_bootefi))
        self.run("mount -t vfat {}2 {}".format(disk, sysroot_bootefi))
        self.run("mkdir -p {}/EFI/Boot".format(sysroot_bootefi))
        self.run("mkdir -p {}/boot/grub2".format(sysroot_bootefi))
        self.run("mkdir -p {}/boot/grub2/fonts".format(sysroot_bootefi))
        self.run("cp /installer/boot/* {}/boot/grub2/fonts/".format(sysroot_bootefi))

        #Setup the disk
        self.run("dd if=/dev/zero of={}/swapfile bs=1M count=64".format(self.photon_root))
        self.run("chmod 600 {}/swapfile".format(self.photon_root))
        self.run("mkswap -v1 {}/swapfile".format(self.photon_root))
        self.run("swapon {}/swapfile".format(self.photon_root))

        if self.default_repo:
            self.run("rm -rf /installer/boot")
            self.run("mkdir -p {}/repo".format(self.photon_root))
            self.progress_bar.show_loading("Unpacking local OSTree repo")
            self.run("tar --warning=none -xf /mnt/cdrom/ostree-repo.tar.gz -C {}/repo".format(self.photon_root))
            self.local_repo_path = "{}/repo".format(self.photon_root)
            self.ostree_repo_url = self.repo_config['OSTREEREPOURL']
            self.ostree_ref = self.repo_config['OSTREEREFS']
            self.progress_bar.update_loading_message("Unpacking done")


        self.deploy_ostree(self.ostree_repo_url, self.ostree_ref)

        self.run("swapoff -a")
        self.run("rm {}/swapfile".format(self.photon_root))

        commit_number = self.get_commit_number(self.ostree_ref)
        self.do_systemd_tmpfiles_commands(commit_number)

        self.mount_devices_in_deployment(commit_number)
        deployment = os.path.join(self.photon_root, "ostree/deploy/photon/deploy/" + commit_number + ".0/")

        deployment_boot = os.path.join(deployment, "boot")
        deployment_sysroot = os.path.join(deployment, "sysroot")

        self.run("mv {} {}".format(loader1, loader0))
        self.run("mv {} {}".format(boot1, boot0))
        self.run("mv {} {}".format(boot11, boot01))
        self.run("mount --bind {} {}".format(sysroot_boot, deployment_boot))
        self.run("mount --bind {} {}".format(self.photon_root, deployment_sysroot))
        # For BIOS Support
        self.run("chroot {} bash -c \"grub2-install --target=i386-pc --force --boot-directory=/boot {}\"".format(deployment, disk_partition))
        # For EFI Support
        self.run("cp /installer/EFI_x86_64/BOOT/* {}/EFI/Boot/".format(sysroot_bootefi))
        self.run("touch {}/boot/grub2/grub.cfg".format(sysroot_bootefi))
        self.run("echo \"search -n -u `blkid -s UUID -o value {}3` -s\" >> {}/boot/grub2/grub.cfg".format(disk, sysroot_bootefi))
        self.run("echo \"configfile /grub2/grub.cfg\" >> {}/boot/grub2/grub.cfg".format(sysroot_bootefi))

        self.run("cp {}/usr/lib/ostree-boot/photon.cfg {}/boot/ ".format(deployment, deployment))
        self.run("cp {}/usr/lib/ostree-boot/systemd.cfg {}/boot/ ".format(deployment, deployment))
        self.run("chroot {} bash -c \"echo load_env -f /photon.cfg >> /etc/grub.d/40_custom \"".format(deployment))
        self.run("chroot {} bash -c \"echo load_env -f /systemd.cfg >> /etc/grub.d/40_custom \"".format(deployment))
        self.run("chroot {} bash -c \"grub2-mkconfig -o /boot/grub2/grub.cfg\"".format(deployment))
        self.run("mv {} {}".format(loader0, loader1))
        self.run("mv {} {}".format(boot0, boot1))
        self.run("mv {} {}".format(boot01, boot11))
        self.run("chroot {} bash -c \"ostree admin instutil set-kargs '\\$photon_cmdline' '\\$systemd_cmdline' root={}4 \"".format(deployment, disk))
        sysroot_grub2_grub_cfg = os.path.join(self.photon_root, "boot/grub2/grub.cfg")
        self.run("ln -sf ../loader/grub.cfg {}".format(sysroot_grub2_grub_cfg))
        self.run("mv {} {}".format(loader1, loader0))
        self.run("mv {} {}".format(boot1, boot0))
        self.run("mv {} {}".format(boot11, boot01))

        deployment_fstab = os.path.join(deployment, "etc/fstab")
        self.run("echo \"{}4    /        ext4   defaults   1 1  \" >> {} ".format(disk, deployment_fstab), "Adding / mount point in fstab")
        self.run("echo \"{}3    /boot    ext4   defaults   1 2  \" >> {} ".format(disk, deployment_fstab), "Adding /boot mount point in fstab")
        self.run("mount --bind {} {}".format(deployment, self.photon_root))
        self.progress_bar.update_loading_message("Starting post install modules")
        self._execute_modules(modules.commons.POST_INSTALL)
        self.progress_bar.update_loading_message("Unmounting disks")
        self.run("{} {} {}".format(Installer.unmount_disk_command, '-w', self.photon_root))
        self.run("{} {} {}".format('umount', '-R', self.photon_root))
        self.progress_bar.update_loading_message("Ready to restart")
        self.progress_bar.hide()
        self.window.addstr(0, 0, 'Congratulations, Photon RPM-OSTree Host has been installed in {0} secs.\n\nPress any key to continue to boot...'.format(self.progress_bar.time_elapsed))
        if 'ui_install' in self.install_config:
            self.window.content_window().getch()
        return ActionResult(True, None)

    def run(self, command, comment = None):
        if comment != None:
            self.logger.info("Installer: {} ".format(comment))
            self.progress_bar.update_loading_message(comment)

        self.logger.info("Installer: {} ".format(command))
        process = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE)
        out,err = process.communicate()
        if err != None and err != 0 and "systemd-tmpfiles" not in command:
            self.logger.error("Installer: failed in {} with error code {}".format(command, err))
            self.logger.error(out)
            self.exit_gracefully(None, None)

        return err
