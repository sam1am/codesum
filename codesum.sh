#!/bin/bash

# Function to add alias to the profile if it doesn't exist
add_alias() {
    local profile_path=$1
    local alias_name=$2
    local script=$3

    # Check if this script is in the profile
    local alias_command="alias ${alias_name}='${script}'"
    if ! grep -q "${alias_command}" "${profile_path}"; then
        echo "${alias_command}" >> "${profile_path}"
        echo "Alias added. You might need to restart your terminal or run 'source ${profile_path}'"
    else
        echo "Alias already exists in your profile"
    fi
}

#get the path of the script
SCRIPT=$(readlink -f "$0")
SCRIPTPATH=$(dirname "$SCRIPT")
GRANDPARENTDIR=$(dirname "$(dirname "$SCRIPTPATH")")

echo "$SCRIPT"
echo "$SCRIPTPATH"
echo "$GRANDPARENTDIR"

#see if virtual environment exists
if [ -f "$SCRIPTPATH/venv/bin/activate" ]; then
    echo "venv exists"
else
    echo "venv does not exist"
    #create virtual environment
    python3 -m venv "$SCRIPTPATH/venv"
    #activate virtual environment
    source "$SCRIPTPATH/venv/bin/activate"
    #install requirements
    pip install -r "$SCRIPTPATH/requirements.txt"
    #deactivate virtual environment
    deactivate
fi

# Alias handling
DECLINE_RECORD=~/.bash_alias_decline
BASH_PROFILE_PATH=~/.bash_profile
BASHRC_PATH=~/.bashrc

# Determine which shell profile exists
if [ -f "$BASH_PROFILE_PATH" ]; then
    PROFILE_PATH="$BASH_PROFILE_PATH"
elif [ -f "$BASHRC_PATH" ]; then
    PROFILE_PATH="$BASHRC_PATH"
else
    echo "No .bash_profile or .bashrc detected. Alias will not be added."
    exit 1
fi

ALIAS_NAME="code_summarize"
ALIAS_EXISTS=$(grep -Fq "alias $ALIAS_NAME=" "$PROFILE_PATH" && echo 'yes' || echo 'no')

# Check if the alias doesn't exist and the user hasn't previously declined
if [[ "$ALIAS_EXISTS" == "no" && ! -f "$DECLINE_RECORD" ]]; then
    echo "Alias not found in your profile. Do you want to add it? (yes/no)"
    read user_input
    if [[ $user_input == 'yes' ]]; then
        add_alias "$PROFILE_PATH" "$ALIAS_NAME" "$SCRIPT"
    elif [[ $user_input == 'no' ]]; then
        # Record the user's decision to not add the alias
        touch "$DECLINE_RECORD"
        echo "Okay, not adding alias. This decision has been remembered."
    fi
fi

# Activate the virtual environment
source "$SCRIPTPATH/venv/bin/activate"

# Run the app
# python "$SCRIPTPATH/app.py"
# Run the app with all command-line arguments passed to this script
python "$SCRIPTPATH/app.py" $@


# Deactivate the virtual environment
deactivate
