#!/usr/bin/python
# Code to update 3d paws software
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

#To stop updates: change environement.py so it will turn off the cron for update_3d_paws.py, thus stopping updates on all current stations. Wait for this update to be pushed out before
#committing the changes that aren't reverse compatable. Change environement.py back before setting up new stations so that they'll still be able to update.

import os, sys, time, urllib.request
root = '/home/pi'
path = root + '/3d_paws'
old_path = path + "_old"
git = 'https://github.com/3d-paws/3d_paws'


#checks for internet connection
def connect():
    try:
        urllib.request.urlopen(git)
        print("Internet found.")
        print()
        if not os.path.exists(root + "/time_check.txt"):
            print("Setting the Real Time Clock...")
            result = os.system("sudo hwclock -w")
            if result == 0:
                with open(root + "/time_check.txt", 'w') as file:
                    file.write("RTC successfully set. Do not delete this file unless you need to reset the RTC.")
                print("RTC successfully set.")
            else:
                print("Failed to set RTC. It is likely not connected.")
            print()
        return True
    except:
        return False


def cleanup(situation): 
    if os.path.exists(path):
        if os.path.exists(old_path):
            print("Finalizing changes...")
            run_command("sudo rm -rf " + old_path, situation)
        if situation != 2:
            print("Update complete!")
            print("Restarting...")
            time.sleep(4)
            os.system("sudo reboot")
    else:
        if os.path.exists(old_path):
            print("Rolling back changes...")
            run_command("sudo mv " + old_path + " " + path, situation)

        
def move(start, end):
    if os.path.exists(start):
        run_command("sudo mv " + start + " " + end)


#runs a command in terminal and checks for issues; extra: 1 = git error, 2 = error while fixing error
def run_command(command, extra=None):
    code = os.system(command)
    if code != 0:
        if extra == 1:
            print("ERROR: Failed to connect to git with exit code %d. Attempting to fix..." %code)
            run_command("sudo apt-get install git")
            run_command(command, 2)
        elif extra != 2:
            print("ERROR: Failed with exit code %d. Attempting to fix (this could take some time)..." %code)
            run_command("sudo apt-get update -y", 2)
            run_command("sudo apt full-upgrade -y", 2)
            print("Pi OS successfully updated. Trying failed step again...")
            run_command(command, 2)
        elif extra == 2:
            print()
            print("ERROR: Could not solve the issue. Command '%s' failed with exit code %d. Please go to %s for detailed instructions, or contact Joey at jrener@ucar.edu for assistance." %(command, code, git))
            print()
            cleanup(2)
            print("Update failed.")
            sys.exit()


#checks current python release
def check_python_version():
    current_version = sys.version_info
    if current_version.major < 3 or (current_version.major == 3 and current_version.minor < 8):
        print("Python 3.8 or higher is required. Currently, Python {}.{} is installed.".format(current_version.major, current_version.minor))
        return False
    print("Correct version of Python installed.")
    return True


#update to Python 3.8
def install_python38():
    print("Installing Python 3.8...")
    os.system("sudo apt-get update --allow-releaseinfo-change")
    os.system("sudo apt-get update && sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl git")
    os.system("curl https://pyenv.run | bash")
    # Add pyenv initializer to shell startup script.
    setup_pyenv_environment()
    home_path = os.path.expanduser('~')
    with open(home_path + '/.bashrc', 'a') as file:
        file.write('\n# Pyenv Initialization\nexport PATH="$HOME/.pyenv/bin:$PATH"\neval "$(pyenv init --path)"\neval "$(pyenv virtualenv-init -)"\n')
    os.system("exec $SHELL")
    os.system("pyenv install 3.8.10")
    os.system("pyenv global 3.8.10")
    print("Python 3.8 installed successfully.")


#used to help with the python update
def setup_pyenv_environment():
    profile_paths = ['/root/.bash_profile', '/root/.profile', '/root/.bashrc']
    pyenv_init_script = """
    # Pyenv Setup
    export PYENV_ROOT="$HOME/.pyenv"
    if [ -d "$PYENV_ROOT/bin" ]; then
        export PATH="$PYENV_ROOT/bin:$PATH"
    fi
    eval "$(pyenv init -)"
    eval "$(pyenv virtualenv-init -)"
    """
    for path in profile_paths:
        with open(path, 'a') as file:
            file.write(pyenv_init_script)
    # The script might need to reload the shell environment or instruct the user to do so.
    print("Pyenv setup appended to shell profiles. Please restart your shell for the changes to take effect.")


#main update sequence
def main():
    #check for internet
    print("Checking for internet...")
    if not connect():
        print("No internet connection found. You must be connected to the internet in order to update software.")
        print()
    else:
        #update to python 3.8 if necessary
        if not check_python_version():
            install_python38()
        #download
        print("Backing up information...")
        #preserve old data
        move(path + "/data/", root + "/data/")
        move(root + "/3d-paws/data/", root + "/data/")
        #preserve old variables
        move(path + "/scripts/input.txt", root + "/Desktop/variables.txt")
        move(root + "/3d-paws/scripts/input.txt", root + "/Desktop/variables.txt")
        #rename old 3d paws folder to fallback on in case update fails
        move(path, old_path)
        print("Backup complete.")
        print()
        #install new 3d paws
        print("Downloading 3D PAWS software package...")
        run_command("sudo git clone https://github.com/3d-paws/3d_paws", 1)
        if os.getcwd() != root:
            move("3d_paws/", path)
        print("Download complete.")
        print()
        #permissions
        print("Updating permissions...")
        run_command("sudo chmod -R a+rwx " + path)
        print("Permissions successfully updated.")
        print()
        #install
        print("Installing dependencies (this could take some time)...")
        run_command("sudo python3 " + path + "/setup.py install")
        run_command("sudo apt-get install lftp")
        print("Dependencies successfully installed.")
        print()
        #cron
        print("Updating cron...")
        run_command("sudo python3 " + path + "/scripts/upkeep/environment.py")
        print("Cron successfully updated.")
        print()
        #finish
        cleanup(None)


main()