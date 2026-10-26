#!/usr/bin/env bash
# Copyright (C) 2026 Jason Froebe
# SPDX-License-Identifier: GPL-3.0-only
# Install the OptiKeep templates from an extracted, verified preview bundle.
# Run with bash: ZIP extraction may not preserve executable permissions.
set -Eeuo pipefail

bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
template_dir=/boot/config/plugins/dockerMan/templates-user

if [[ "$EUID" != 0 ]]; then
    echo 'Run this installer as root: bash install-template.sh' >&2
    exit 1
fi

if [[ ! -d "$template_dir" || ! -d /usr/local/emhttp ]]; then
    echo 'The expected Unraid Docker manager directories were not found.' >&2
    exit 1
fi

# Resolve files beside this script, even when invoked from another directory.
cd -- "$bundle_dir"
for required in SHA256SUMS install-template.sh my-OptiKeep.xml my-OptiKeep-Worker.xml; do
    if [[ ! -f "$required" ]]; then
        printf 'Required bundle file is missing: %s\n' "$required" >&2
        exit 1
    fi
done

# Require hashes for the installer and both templates, then verify the whole
# bundle before touching installed templates. The Docker image is not loaded.
for required in install-template.sh my-OptiKeep.xml my-OptiKeep-Worker.xml; do
    if ! awk -v name="$required" '$2 == name && length($1) == 64 {found=1} END {exit !found}' SHA256SUMS; then
        printf 'Checksum entry is missing: %s\n' "$required" >&2
        exit 1
    fi
done
sha256sum --strict -c SHA256SUMS

# Preserve customized templates before replacing them. Identical templates
# require no write and create no extra backup on a repeated installation.
backup_dir=''
for template in my-OptiKeep.xml my-OptiKeep-Worker.xml; do
    destination="$template_dir/$template"
    if [[ -e "$destination" || -L "$destination" ]]; then
        if [[ -L "$destination" || ! -f "$destination" ]]; then
            printf 'Refusing a non-regular template destination: %s\n' "$destination" >&2
            exit 1
        fi
        if cmp -s -- "$template" "$destination"; then
            continue
        fi
        if [[ -z "$backup_dir" ]]; then
            backup_dir="$(mktemp -d "$template_dir/optikeep-backup.XXXXXXXX")"
        fi
        cp -p -- "$destination" "$backup_dir/$template"
    fi
done

for template in my-OptiKeep.xml my-OptiKeep-Worker.xml; do
    destination="$template_dir/$template"
    if ! cmp -s -- "$template" "$destination"; then
        install -m 0644 -- "$template" "$destination"
    fi
done
if [[ -n "$backup_dir" ]]; then
    printf 'Previous templates saved in: %s\n' "$backup_dir"
fi
echo 'OptiKeep coordinator and worker templates installed.'
echo 'In Unraid Docker > Add Container, select OptiKeep and OptiKeep-Worker.'
echo 'Load the Docker image and configure appdata, media and tokens as described in README.md.'
