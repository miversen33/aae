#!/usr/bin/bash

# To run this, curl /enroll into bash. EG
# sudo sh -c "bash <(curl -Lfs https://pmtools.interpublic.com/ansible/enroll)"
#
# If you want the script to auto enroll minimal information, you can add the AUTOMATED variable into the call. EG
# sudo sh -c "AUTOMATED=1 bash <(curl -Lfs https://pmtools.interpublic.com/ansible/enroll)"

DEBUG="${DEBUG:=1}"

SSHD_CONFIG=/etc/ssh/sshd_config
SSHD_CONFIG_BACKUP=/tmp/sshd_config_$(date +%Y%m%d%H%M%S)
# This will be dynamically populated by the server
SSH_PUBKEY_LINK=
SSH_AUTH_KEYS="${HOME}/.ssh/authorized_keys"

# This will be dynamically populated by the server
ENROLL_LINK=

# This will be dynamically populated by the server
ENVIRONMENTS=

HOSTNAME=$(cat /etc/hostname)
APPLICATIONS="${APPLICATIONS:=}"
ENVIRONMENT="${ENVIRONMENT:=}"
AUTOMATED="${AUTOMATED:=0}"

error(){
    msg="$1"
    echo -e "\033[31m${msg}\033[0m"
}

debug(){
    msg="$1"
    if [ "${DEBUG}" == "1" ]; then
        echo "${msg}"
    fi
}

if [ $UID != 0 ]; then
    error "You must be root to enroll!"
    exit 1
fi

backup_ssh_config(){
    debug "Backing up ${SSHD_CONFIG} to ${SSHD_CONFIG_BACKUP}"
    cp "${SSHD_CONFIG}" "${SSHD_CONFIG_BACKUP}"
}

revert_ssh_config(){
    debug "Restoring ${SSHD_CONFIG}"
    mv "${SSHD_CONFIG_BACKUP}" "${SSHD_CONFIG}"
}

cleanup(){
    debug "Cleaning up after ourselves"
    rm -f "${SSHD_CONFIG_BACKUP}"
}

validate_ssh_config(){
    if grep -qE '#PubkeyAuthentication' $SSHD_CONFIG; then
        debug "PubkeyAuthentication is currently disabled via comment. Fixing that"
        sed --expression 's/^#PubkeyAuthentication.*/PubkeyAuthentication yes/g' -i $SSHD_CONFIG
        if [ $? != 0 ]; then
            error "Unable to update ssh configuration! Reverting now"
            revert_ssh_config
            exit 10
        fi
    fi
    if grep -qE '^"PubkeyAuthentication\s*no' $SSHD_CONFIG; then
        debug "PubkeyAuthentication is currently disabled via setting. Fixing that"
        sed --expression 's/^PubkeyAuthentication.*/PubkeyAuthentication yes/g' -i $SSHD_CONFIG
        if [ $? != 0 ]; then
            error "Unable to update ssh configuration! Reverting now"
            revert_ssh_config
            exit 11
        fi
    fi
}

get_ssh_key(){
    env="$1"
    pubkey=$(curl -Lfs "${SSH_PUBKEY_LINK}/${env}")
    touch "${SSH_AUTH_KEYS}"
    if ! grep -qF "${pubkey}" "${SSH_AUTH_KEYS}"; then
        debug "Ansible pubkey not found in root authorized keys. Fixing that"
        echo "${pubkey}" >> "${SSH_AUTH_KEYS}"
    fi
}

enroll(){
    debug "Enrolling ${HOSTNAME} into ansible"
    get_ssh_key "${ENVIRONMENT}"
    enroll_link="${ENROLL_LINK}?hostname=${HOSTNAME}&environment=${ENVIRONMENT}&applications=${APPLICATIONS}" >/dev/null # For some reason this is printing null into the console...?
    debug "Enrolling with link: ${enroll_link}"
    curl -Lfs "${enroll_link}"
}

interactive_mode(){
    debug "Running setup in interactive mode!"
    has_environment=1
    envs=$(printf ", \"%s\"" "${ENVIRONMENTS[@]}")
    envs="${envs:1}"
    while [ $has_environment = 1 ]; do
        echo "Current selected environment is \"${ENVIRONMENT}\". Available environments are ->${envs}"
        read -rp "Environment: " -a new_env
        _new_env=$(echo "${new_env}" | tr "[:upper:]" "[:lower:]")
        for env in "${ENVIRONMENTS[@]}"; do
            env=$(echo "${env}" | tr "[:upper:]" "[:lower:]")
            if [ "${env}" = "${_new_env}" ]; then
                has_environment=0
                break
            fi
        done
        if [ $has_environment ]; then
            echo "Selected New Environment: ${new_env}"
        fi
    done
    ENVIRONMENT="${new_env}"

    has_applications=1
    _apps=${APPLICATIONS[@]}
    while [ $has_applications = 1 ]; do
        apps=$(printf ", \"%s\"" "${_apps[@]}")
        apps="${apps:1}"
        read -rp "Currently selection applications are ->${apps}. Do you wish to set any applications on this server? [y/N] " -a response
        if [ "$response" = "n" ] || [ "$response" = "" ]; then
            debug "Skipping application setting"
            break
        fi
        read -rp "Applications: " _apps
        _apps=$(echo "${_apps}" | sed --expression 's/[, ]\+/ /g')
         read -rp "Are you ready to continue? [Y/n]" -a response
        if [ "$response" = "y" ] || [ "$response" = "" ]; then
            has_applications=0
        fi
        apps=()
        read -a apps <<< "$_apps"
    done
    if [ $has_applications = 0 ]; then
        apps=$(printf ",%s" "${apps[@]}")
        APPLICATIONS="${apps:1}"
    fi
    enroll
}

automated_mode(){
    debug "Running setup in automated mode!"
    enroll
}

backup_ssh_config
validate_ssh_config
if [ $AUTOMATED = 1 ]; then
    automated_mode
else
    interactive_mode
fi
cleanup
