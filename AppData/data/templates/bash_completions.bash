#!/bin/bash

# It would have been impossible to create this without the following post on Stack Exchange!!!
# https://unix.stackexchange.com/a/55622

_have {executable_name} &&
_decide_nospace_{current_date}(){
    if [[ ${1} == "--"*"=" ]] ; then
        compopt -o nospace
    fi
} &&
_list_dirs(){
    # <3 https://stackoverflow.com/a/31603260
    # List all directories found inside the passed folder ($1).
    # WARNING! Fails on empty directories!
    (
        cd "${1}" && \
        set -- */; printf "%s\n" "${@%/}";
    )
} &&
__hosts_manager_app_{current_date}(){
    local cur prev cmd profiles_dir profiles override_keys
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    profiles_dir="{full_path_to_app_folder}/UserData/profiles"
    profiles=( $(_list_dirs ${profiles_dir}) )
    override_keys=("target_ip=0.0.0.0"
"keep_domain_comments=false"
"skip_static_hosts=false"
"backup_old_generated_hosts=true"
"backup_system_hosts=true"
"max_backups_to_keep=10")

    case $prev in
        --profile)
            COMPREPLY=( $( compgen -W "${profiles[*]}") )
            return 0
            ;;
        -p)
            COMPREPLY=( $( compgen -W "${profiles[*]}" -- ${cur}) )
            return 0
            ;;
        --override)
            COMPREPLY=( $( compgen -W "${override_keys[*]}") )
            return 0
            ;;
        -o)
            COMPREPLY=( $( compgen -W "${override_keys[*]}" -- ${cur}) )
            return 0
            ;;
    esac

    # Handle --xxxxx=path
    if [[ ${prev} == "=" ]] ; then
        # Unescape space
        cur=${cur//\\ / }

        if [[ ${cur} != *"/"* ]]; then
            COMPREPLY=( $( compgen -W "${profiles[*]}" -- ${cur}) )
            return 0
        fi

        return 0
    fi

    # Completion of commands and "first level options.
    if [[ $COMP_CWORD == 1 ]]; then
        COMPREPLY=( $(compgen -W "run server generate -d --flush-dns-cache -h --help --version" -- "${cur}") )
        return 0
    fi

    # Completion of options and sub-commands.
    cmd="${COMP_WORDS[1]}"

    case $cmd in
    "run")
        COMPREPLY=( $(compgen -W "update build install -d --flush-dns-cache -p --profile= \
-o --override= -f --force-update" -- "${cur}") )
        _decide_nospace_{current_date} ${COMPREPLY[0]}
        ;;
    "server")
        COMPREPLY=( $(compgen -W "start stop restart --host= --port=" -- "${cur}") )
        _decide_nospace_{current_date} ${COMPREPLY[0]}
        ;;
    "generate")
        COMPREPLY=( $(compgen -W 'system_executable new_profile' -- "$cur" ) )
        return 0
        ;;
    esac
} &&
complete -F __hosts_manager_app_{current_date} {executable_name}
