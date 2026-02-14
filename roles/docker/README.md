# docker

Ansible role to clean up Docker resources.

## Description

This role prunes unused Docker resources to free up disk space:
- Containers older than 24 hours
- Unused images
- Unused networks
- Unused volumes
- Builder cache

## Requirements

- Docker Desktop installed and running
- `community.docker` Ansible collection

## Role Variables

This role has no configurable variables. It performs a full cleanup of unused Docker resources.

## Dependencies

- Docker must be installed and running

## Example Playbook

```yaml
- hosts: all
  roles:
    - role: docker
```

## Tags

- `docker`

## What Gets Cleaned

| Resource   | Criteria                          |
|------------|-----------------------------------|
| Containers | Stopped containers older than 24h |
| Images     | Unused/dangling images            |
| Networks   | Unused networks                   |
| Volumes    | Unused volumes                    |
| Builder    | Build cache                       |

## Notes

- This role does NOT install Docker - use the `brew` role with `docker-desktop` cask
- Running containers and their resources are not affected
- Use with caution in production environments
