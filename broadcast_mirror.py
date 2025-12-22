#!/usr/bin/env python3
import os
import sys
import argparse
import time
import requests
import dotenv

LICHESS_BASE = "https://lichess.org"

dotenv.load_dotenv()


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "lichess-broadcast-clone-lila/1.0",
        }
    )
    return s


def post_session(token: str | None) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "User-Agent": "lichess-broadcast-clone-lila/1.0",
        }
    )
    return s


def fetch_broadcast_tournament(session: requests.Session, tour_id: str) -> dict:
    print(f"Fetching source tournament {tour_id} from {LICHESS_BASE}...")
    url = f"{LICHESS_BASE}/api/broadcast/{tour_id}"
    r = session.get(url)
    r.raise_for_status()
    return r.json()


def create_local_tournament(
    local_base: str, session: requests.Session, tour: dict
) -> dict:
    print("Creating tournament on local instance...")
    tour_info: dict = tour.get("tour", {})
    name: str = tour_info.get("name", "Broadcast")
    description: str = tour_info.get("description", "")
    info = tour_info.get("info", {})
    fideTc: str | None = info.get("fideTc")
    format: str | None = info.get("format")
    location: str | None = info.get("location")
    players: str | None = info.get("players")
    tc: str | None = info.get("tc")
    standings: str | None = info.get("standings")
    timezone: str | None = info.get("timezone")
    website: str | None = info.get("website")
    teamTable: bool | None = tour_info.get("teamTable")
    form = {
        "name": name,
        "description": description,
        "visibility": "public",
        "info.fideTc": fideTc,
        "info.format": format,
        "info.tc": tc,
        "info.location": location,
        "info.players": players,
        "info.standings": standings,
        "info.timezone": timezone,
        "info.website": website,
        "teamTable": "true" if teamTable else "false",
        "showScores": "true",
        "showRatingDiffs": "true",
    }
    url = f"{local_base.rstrip('/')}/broadcast/new"
    r = session.post(
        url, data=form, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    r.raise_for_status()
    return r.json()


def fetch_round_pgn(session: requests.Session, round_id: str) -> str:
    url = f"{LICHESS_BASE}/api/broadcast/round/{round_id}.pgn"
    r = session.get(url)
    r.raise_for_status()
    return r.text


def create_local_round(
    local_base: str,
    session: requests.Session,
    local_tour_id: str,
    round: dict,
    tour: dict,
) -> dict:
    name: str = round.get("name", "Round")
    rated: bool = round.get("rated", True)
    customScoring: dict = round.get("customScoring", {})
    tiebreaks: list = tour.get("tiebreaks", [])
    form: dict[str, object] = {
        "name": name,
        "syncSource": "push",
        "rated": "true" if rated else "false",
        "tiebreaks[]": tiebreaks,
    }
    if customScoring:
        for color in ["white", "black"]:
            for result in ["win", "draw"]:
                key = f"customScoring.{color}.{result}"
                form[key] = customScoring.get(color, {}).get(result, None)
    url = f"{local_base.rstrip('/')}/broadcast/{local_tour_id}/new"
    r = session.post(
        url, data=form, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    r.raise_for_status()
    return r.json()


def push_pgn_to_round(
    post_session: requests.Session, local_base: str, round_id: str, pgn: str
) -> dict:
    url = f"{local_base.rstrip('/')}/api/broadcast/round/{round_id}/push"
    # text/plain body
    r = post_session.post(
        url, data=pgn.encode("utf-8"), headers={"Content-Type": "text/plain"}
    )
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(
        description="Clone a Lichess broadcast tournament to a local instance and push PGN"
    )
    parser.add_argument(
        "--tour-id", help="Broadcast tournament ID on lichess.org (8 chars)"
    )
    parser.add_argument(
        "--local-lila",
        default=os.environ.get("LOCAL_LICHESS_BASE", "http://localhost:9663"),
        help="Local Lichess base URL",
        required=False,
    )
    args = parser.parse_args()
    local_token = os.environ.get("LOCAL_LICHESS_TOKEN")
    tour_id = args.tour_id
    local_lila = args.local_lila

    if not local_token:
        print(
            "Error: Local token is required (set LOCAL_LICHESS_TOKEN)",
            file=sys.stderr,
        )
        sys.exit(1)

    session = get_session()
    local_session = post_session(local_token)

    tour = fetch_broadcast_tournament(session, tour_id)
    local_tour = create_local_tournament(local_lila, local_session, tour)
    local_tour_id = local_tour.get("tour", {}).get("id")
    if not local_tour_id:
        print("Error: Could not determine local tournament ID", file=sys.stderr)
        sys.exit(1)
    print(f"Local tournament created: {local_tour_id}")

    source_rounds = tour.get("rounds", [])
    if not source_rounds:
        print("No rounds found in source tournament.")

    created_rounds = []
    for idx, src_round in enumerate(source_rounds, start=1):
        src_round_id = src_round.get("id")
        print(f"Creating round {idx} on local...")
        local_round = create_local_round(
            local_lila, local_session, local_tour_id, src_round, tour
        )
        local_round_id = local_round.get("round", {}).get("id") or local_round.get("id")
        if not local_round_id:
            print("Warning: Could not determine local round ID; skipping PGN push.")
            continue
        elif not src_round.get("finished") or src_round.get("ongoing"):
            print("Source round not started. Skipping PGN push")
            continue

        print(f"Fetching PGN for source round {src_round_id}...")
        pgn = fetch_round_pgn(session, src_round_id)
        time.sleep(1)

        print(f"Pushing PGN to local round {local_round_id}...")
        push_res = push_pgn_to_round(local_session, local_lila, local_round_id, pgn)
        created_rounds.append(
            {
                "source_round_id": src_round_id,
                "local_round_id": local_round_id,
                "push_result": push_res,
            }
        )

    print("Done. Summary:")
    print(
        {
            "local_tournament_id": local_tour_id,
            "rounds": created_rounds,
        }
    )


if __name__ == "__main__":
    main()
