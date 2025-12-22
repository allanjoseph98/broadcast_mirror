# Why?

Utility to quickly clone a broadcast from [lichess](https://lichess.org) to a local lila instance.
For those of us without root access to many or broadcast sources.

# Usage:

1. pip install -r requirements.txt
2. Run your local lila instance
3. Obtain an Oauth2 token with `study:write` perms for the account from which you wish to create the broadcast on your _local_ instance
4. Add the token to a .env file `LOCAL_LICHESS_TOKEN=lip_abc...`
5. Run ./broadcast_mirror.py

Args:

- --tour-id: The tournament ID of the broadcast you want to clone from lichess.org
- --local-lila: The URL of your local Lila instance. `localhost:8080` if running on [lila-docker](github.com/lichess-org/lila-docker) or `localhost:9663` if running manually. Default=`localhost:9663`
