#!/bin/bash

# Function to install Python3 and Pip3 on Ubuntu
install_ubuntu() {
    sudo apt update -y
    if ! command -v python3 &> /dev/null || ! command -v pip3 &> /dev/null
    then
        echo "Python3 and/or pip3 could not be found"
        echo "Installing Python3 and pip3 ..."
        sudo apt install python3 python3-pip -y
    fi
}

# Function to install Python3 and Pip3 on Windows
install_windows() {
    if ! command -v python &> /dev/null || ! command -v pip &> /dev/null
    then
        echo "Python and/or pip could not be found"
#        echo "Installing Python and pip ..."
        # Chocolatey:
        # choco install python -y
        # Scoop:
        # scoop install python
        echo "Please install Python and pip manually."
        exit 1
    fi
}

# Function to install Python3 and Pip3 on MacOS
install_mac() {
    if ! command -v python3 &> /dev/null || ! command -v pip3 &> /dev/null
    then
        echo "Python3 and/or pip3 could not be found"
#        echo "Installing Python3 and pip3 ..."
        # Homebrew:
        # brew install python
        # MacPorts:
        # port install python3
        echo "Please install Python and pip manually."
        exit 1
    fi
}

# Detect the operating system and call the appropriate installation function
case "$(uname -s)" in
    Linux*)     install_ubuntu ;;
    Darwin*)    install_mac ;;
    CYGWIN*)    install_windows ;;
    MINGW*)     install_windows ;;
    *)          echo "Unsupported operating system" ;;
esac

# Install Python packages using pip
pip3 install -r requirements.txt

echo "Now run everything follow the instruction from README.md"