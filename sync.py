import proxmoxer
import ldap
import logging
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
logging.basicConfig(level=logging.INFO)

if not os.environ.get("PVE_DEST_REALM"):
    print("Destination realm required")
    sys.exit(1)

dest_realm = os.environ.get("PVE_DEST_REALM")

# get CA bundle path
if os.environ.get("CA_BUNDLE"):
    ca_bundle_path = Path(os.environ.get("CA_BUNDLE")).resolve()

# do ldap query
try:
    if ca_bundle_path:
        ldap.set_option(ldap.OPT_X_TLS_CACERTFILE, str(ca_bundle_path))
    elif os.environ.get("TLS_VERIFY", True):
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
    ldapobj = ldap.initialize(os.environ.get("LDAP_URI"))
    ldapobj.simple_bind_s(os.environ.get("LDAP_USER"), os.environ.get("LDAP_PASS"))
except ldap.INVALID_CREDENTIALS:
    print("Invalid credentials")
    sys.exit(1)
except ldap.LDAPError as e:
    print(e)
    sys.exit(1)

# get LDAP membership
results = ldapobj.search_s(
    os.environ.get("LDAP_BASE_DN"),
    ldap.SCOPE_SUBTREE,
    os.environ.get("LDAP_SEARCH_FILTER"),
    ["dn"],
)

proxmox = proxmoxer.ProxmoxAPI(
    os.environ.get("PVE_HOST"),
    user=os.environ.get("PVE_USER"),
    password=os.environ.get("PVE_PASS"),
    verify_ssl=ca_bundle_path if ca_bundle_path else False,
)

proxmox_openid_users = [
    user["userid"]
    for user in proxmox.access.users.get()
    if user["realm-type"] == "openid"
]
proxmox_openid_groups = [
    group["groupid"]
    for group in proxmox.access.groups.get()
    if dest_realm in group["groupid"]
]

user_group_assoc = {}
groups_to_create = []
groups_to_delete = []

# parse through LDAP membership and assemble list for Proxmox
for result in results:
    group_dn, params = result
    groupid = f"{group_dn.split(',')[0].split('=')[1]}-{dest_realm}"
    if groupid not in proxmox_openid_groups:
        groups_to_create.append(groupid)

    # use subLDAP query in order to pull nested members since Proxmox doesn't support nested group membership
    # this query only works on non-LDAP systems that support nested group membership. AD requires a different LDAP query
    user_member_query_result = ldapobj.search_s(
        os.environ.get("LDAP_BASE_DN"),
        ldap.SCOPE_SUBTREE,
        f"(&(objectClass=person)(memberOf={group_dn}))",
        ["dn"],
    )

    user_members = [user_dn[0] for user_dn in user_member_query_result]
    for user_dn in user_members:
        user = f"{user_dn.split(',')[0].split('=')[1]}@{dest_realm}"
        if user not in user_group_assoc:
            user_group_assoc[user] = [groupid]
        else:
            user_group_assoc[user].append(groupid)

# create groups
for group in groups_to_create:
    logging.info("Creating group: %s", group)
    proxmox.access.groups.post(
        groupid=group, comment="LDAP/OpenID Sync Managed DO NOT EDIT"
    )

# map users
for user, groups in user_group_assoc.items():
    if user not in proxmox_openid_users:
        logging.info("Creating user: %s with groups: %s", user, groups)
        proxmox.access.users.post(userid=user, enable=1, groups=groups)
    else:
        logging.info("Syncing user groups for user: %s with groups: %s", user, groups)
        proxmox.access.users(user).put(groups=groups)
