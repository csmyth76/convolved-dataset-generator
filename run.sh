#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

venv="${this_dir}/.venv"
if [[ -d "${venv}" ]]; then
    echo "Using virtual environment at ${venv}"
    source "${venv}/bin/activate"
fi

export PATH="${this_dir}/bin:${PATH}"

doit "$@"
