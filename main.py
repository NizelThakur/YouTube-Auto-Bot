#!/usr/bin/env python3
import argparse
import os
import sys

from src.bot.pipeline import Pipeline


def get_profiles():
    profiles_dir = os.path.join(os.path.dirname(__file__), "profiles")
    if not os.path.isdir(profiles_dir):
        return []
    return [
        d for d in sorted(os.listdir(profiles_dir))
        if os.path.isdir(os.path.join(profiles_dir, d))
        and os.path.exists(os.path.join(profiles_dir, d, "config.json"))
    ]


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Bot")
    parser.add_argument("--profile", default=None, help="Single profile to run")
    parser.add_argument("--all", action="store_true", help="Run all profiles")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual YouTube upload")
    args = parser.parse_args()

    if args.all:
        profiles = get_profiles()
        if not profiles:
            print("ERROR: No profiles found in profiles/ directory!")
            sys.exit(1)
    elif args.profile:
        profiles = [args.profile]
    else:
        print("ERROR: Specify --profile <name> or --all")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"\n{'='*55}")
    print(f"  YOUTUBE SHORTS BOT")
    print(f"  Profiles: {', '.join(profiles)}")
    print(f"  Dry Run: {args.dry_run}")
    print(f"{'='*55}\n")

    failures = []
    for profile in profiles:
        try:
            Pipeline(profile, base_dir).run(dry_run=args.dry_run)
        except Exception as e:
            print(f"\n[FAILED] Profile '{profile}': {e}\n")
            failures.append(profile)

    print(f"\n{'='*55}")
    print(f"  DONE | Success: {len(profiles) - len(failures)} | Failed: {len(failures)}")
    print(f"{'='*55}\n")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
