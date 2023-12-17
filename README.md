# Proxmox OIDC LDAP Sync

This script is designed to sync users from an LDAP server to a Proxmox OIDC realm.

Proxmox doesn't have any existing user matching between LDAP users and OIDC users, nor can they parse
group claims from the OIDC login, thus requiring admins to manually assign groups by creating an OIDC
user or by waiting for the user to login before assigning groups.

## Installation

You will need `libsasl2-dev`, `libssl-dev`, and `libldap-dev` on Debian to install `python-ldap`
through `pip`.

```bash
pip install -r requirements.txt
```

### Systemd service
I've provided some generic systemd templates for the service and a daily timer. Install these by
copying them to your `/etc/systemd/system` directory and performing a `systemctl daemon-reload`.

Remember to update the files with values to match your environment.

## Environment Variables

* `TLS_VERIFY` - (default: True): Determines if LDAP should verify SSL certificates.
* `CA_BUNDLE` - Location of CA certificates to use during verification for LDAP and Proxmox connections.


* `PVE_HOST` - Proxmox VE hostname. If SSL is in use, the value must match the SUBJ or SAN in the certificate.
* `PVE_USER` - Proxmox VE user used to update/modify user/groups. The user must have `PVEUserAdmin` over `/access/groups` and `/access/realm/{PVE_DEST_REALM}`.
* `PVE_PASS` - Proxmox VE user password
* `PVE_DEST_REALM` - OIDC Realm


* `LDAP_URI` - LDAP Server (e.g., `ldaps://host.example.com`)
* `LDAP_USER` - Unprivileged LDAP user to accomplish queries
* `LDAP_PASS` - LDAP password
* `LDAP_BASE_DN` - Base DN to search
* `LDAP_SEARCH_FILTER` - LDAP filter for **groups** that the script should sync to Proxmox.
