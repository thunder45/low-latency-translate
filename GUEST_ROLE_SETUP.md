# Guest Role Setup for Identity Pool

## The Trust Policy Warning

The warning appears because KVSClientRole was created for **authenticated** users only. Its trust policy checks for `"cognito-identity.amazonaws.com:amr": "authenticated"`.

For guest access, you need a role with trust policy checking for `"unauthenticated"`.

## Solution: Let Cognito Create Guest Role

**Easiest**: Let AWS console create a new role automatically:

1. In Identity Pool settings → Guest access
2. Click "Create a new IAM role"
3. Name it: `KVSWebRTC-dev-GuestRole`
4. AWS will generate proper trust policy with KVS permissions

The console will copy permissions from the authenticated role automatically.

## Alternative: Use KVSClient Role with Updated Trust

Not recommended - simpler to have separate roles for authenticated vs guest.

## After Creating Guest Role

Test listener app - it should now get credentials and connect to KVS!
